"""Casos de uso de los pagos.

Por pagar: el gerente y todas sus asistentes ven las cuotas del espacio que faltan pagarse, de las
deudas registradas (las que esperan autorización no se pagan).

Subir un comprobante: para una cuota que falta pagarse. Se valida el archivo por su contenido, se
guarda cifrado y el análisis corre en el worker, que lo compara con la cuota. Si no corresponde
(repetido, alterado, de otra deuda), queda un intento: al tercero en 24 horas se bloquea el
registro de pagos de la asistente y se avisa al gerente, que es quien lo levanta. Los ilegibles no
cuentan. Al gerente nunca se le bloquea.

Registrar el pago: con los comprobantes listos de esa cuota que subió la misma cuenta. El backend
vuelve a comprobar todo, con la deuda tomada con FOR UPDATE: la cuota sin otro pago, la suma de los
comprobantes igual a la cuota, varios solo de un agente y del mismo día. El de una asistente queda
por verificar y se avisa al gerente con la confianza calculada; el del gerente queda confirmado.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import exigir_cupo
from app.acceso.dominio.errores import ServicioNoDisponible, SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite, Reloj
from app.categorias.aplicacion.categorias import espacio_de
from app.deudas.aplicacion.deudas import formatear_fecha
from app.deudas.dominio.errores import DeudaNoEncontrada
from app.deudas.dominio.modelos import Cuota, Deuda, EstadoDeuda, EstadoPago, LugarPago
from app.documentos.aplicacion.documentos import huella_archivo
from app.documentos.dominio.analisis import evaluar_metadatos, normalizar_numero, senal_veredicto
from app.documentos.dominio.archivos import limpiar_nombre, validar_archivo
from app.documentos.dominio.bloqueos import Bloqueo, contar_desde
from app.documentos.dominio.errores import AsistenteNoEncontrada
from app.documentos.dominio.modelos import Lectura, Riesgo, Senal, TipoArchivo
from app.documentos.dominio.puertos import (
    Almacen,
    ErrorAlmacen,
    ErrorCola,
    ErrorRevision,
    Huellero,
    InspectorArchivos,
    LectorTexto,
)
from app.notificaciones.aplicacion.notificaciones import Avisos
from app.notificaciones.dominio.modelos import Notificacion, TipoNotificacion, nueva_notificacion
from app.notificaciones.dominio.puertos import PublicadorAvisos
from app.pagos.dominio.confianza import CRITERIOS_MORA, comprobaciones, confianza
from app.pagos.dominio.errores import (
    BloqueoPagosNoEncontrado,
    CamposFaltantes,
    ComprobanteNoEncontrado,
    ComprobanteNoUsable,
    ComprobantesNoCombinan,
    CuotaNoPagable,
    ImporteNoCoincide,
    MoraNoEncontrada,
    PagoInvalido,
    PagoNoEncontrado,
    PedidoNoEncontrado,
    RegistroPagosBloqueado,
)
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    Comprobacion,
    Comprobante,
    DatosComprobante,
    EstadoComprobante,
    EstadoMora,
    Moneda,
    Mora,
    Pago,
    Pedido,
    Proposito,
    ResultadoComprobacion,
)
from app.pagos.dominio.puertos import (
    ColaComprobantes,
    FabricaUnidadPagos,
    RevisorComprobantes,
    UnidadPagos,
)
from app.pagos.dominio.reglas import (
    MAXIMO_COMPROBANTES,
    MAXIMO_RECHAZADOS,
    CuotaEsperada,
    comparar_mora,
    cuenta_para_bloqueo,
    estado_tras_analisis,
    evaluar,
    evaluar_prueba_mora,
    senal_datos_a_mano,
    senal_ilegible,
    senal_legibilidad,
    senal_repetido,
)
from app.reglas.dominio.importes import a_importe, error_importe, formatear_soles

logger = logging.getLogger(__name__)

LARGO_MOTIVO = 500
LARGO_MOTIVO_EN_AVISO = 280

ESTADOS_COMPROBANTE = {
    EstadoComprobante.ANALIZANDO: "COMPROBANTE_EN_ANALISIS",
    EstadoComprobante.ILEGIBLE: "COMPROBANTE_ILEGIBLE",
    EstadoComprobante.RECHAZADO: "COMPROBANTE_RECHAZADO",
    EstadoComprobante.REPETIDO: "COMPROBANTE_REPETIDO",
    EstadoComprobante.FALLIDO: "COMPROBANTE_FALLIDO",
}


def esperada_de(
    uow: UnidadPagos, deuda: Deuda, cuota: Cuota, hoy: date, zona: ZoneInfo
) -> CuotaEsperada:
    documento = uow.documentos.por_id(deuda.documento_id)
    leidos = documento.analisis.datos if documento and documento.analisis else None
    mora = uow.moras.de_la_cuota(deuda.id, cuota.numero)
    return CuotaEsperada(
        importe=cuota.importe,
        codigo_pago=deuda.codigo_pago,
        empresa=leidos.emisor if leidos else None,
        titular=deuda.titular_nombre,
        lugares=deuda.lugares_pago,
        registrada_el=deuda.creado_en.astimezone(zona).date(),
        vencida=cuota.vence_el < hoy,
        mora=mora.importe if mora and mora.estado is EstadoMora.APROBADA else None,
    )


def anotar_rechazo(
    uow: UnidadPagos,
    avisos: Avisos,
    reloj: Reloj,
    asistente_id: UUID,
    gerente_id: UUID,
    comprobante_id: UUID,
) -> bool:
    """Deja constancia del comprobante que no corresponde y, si es el tercero en 24 horas, bloquea
    el registro de pagos de la asistente y avisa a su gerente. Devuelve True si quedó bloqueada."""
    ahora = reloj()
    uow.bloqueos.registrar_intento(asistente_id, comprobante_id, ahora)
    uow.auditoria.registrar(
        EventoAuditoria(
            Accion.COMPROBANTE_RECHAZADO,
            actor_id=asistente_id,
            detalle={"comprobante_id": str(comprobante_id)},
        )
    )
    desde = contar_desde(ahora, uow.bloqueos.ultimo_levantamiento(asistente_id))
    if uow.bloqueos.contar_intentos(asistente_id, desde) < MAXIMO_RECHAZADOS:
        return False
    bloqueo = Bloqueo(uuid4(), asistente_id, gerente_id, ahora)
    if not uow.bloqueos.bloquear(bloqueo):
        return True
    uow.auditoria.registrar(
        EventoAuditoria(
            Accion.REGISTRO_PAGOS_BLOQUEADO,
            cuenta_id=asistente_id,
            detalle={"intentos": MAXIMO_RECHAZADOS},
        )
    )
    avisos.guardar(
        uow.notificaciones,
        nueva_notificacion(
            gerente_id,
            TipoNotificacion.REGISTRO_PAGOS_BLOQUEADO,
            f"bloqueo-pagos:{bloqueo.id}",
            "Bloqueamos el registro de pagos de tu asistente",
            f"Subió {MAXIMO_RECHAZADOS} comprobantes en 24 horas que no correspondían a sus "
            "cuotas. Revisa lo ocurrido y, si corresponde, permítele registrar pagos otra vez "
            "desde Mi equipo.",
            ahora,
            cuenta_id=asistente_id,
        ),
    )
    return True


class _OperacionPagos:
    def __init__(
        self,
        unidad: FabricaUnidadPagos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        zona: ZoneInfo,
    ) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._publicador = publicador
        self._limitador = limitador
        self._limite = limite
        self._zona = zona

    def _hoy(self) -> date:
        return self._reloj().astimezone(self._zona).date()

    def _cupo(self, sesion: SesionActiva) -> None:
        exigir_cupo(self._limitador, (self._limite, str(sesion.usuario.id)))

    @staticmethod
    def _sin_bloqueo(uow: UnidadPagos, sesion: SesionActiva) -> None:
        """Una tras otra por cuenta: el bloqueo y los intentos se comprueban sin carreras."""
        usuario = sesion.usuario
        uow.cuentas.bloquear_cuenta(usuario.id)
        if usuario.rol is Rol.ASISTENTE and (bloqueo := uow.bloqueos.vigente(usuario.id)):
            raise RegistroPagosBloqueado(bloqueo.bloqueado_en)

    def _cuota_por_pagar(
        self,
        uow: UnidadPagos,
        sesion: SesionActiva,
        deuda_id: UUID,
        numero: int,
        *,
        bloquear: bool,
        proposito: Proposito = Proposito.PAGO,
    ) -> tuple[Deuda, Cuota]:
        """La cuota sin pago de una deuda registrada del espacio. Para pagarla, sin una mora que
        espere aprobación; para declarar su mora, vencida y sin otra mora vigente."""
        deuda = uow.deudas.por_id(deuda_id, bloquear=bloquear)
        if deuda is None or deuda.gerente_id != espacio_de(sesion):
            raise DeudaNoEncontrada()
        if deuda.estado is EstadoDeuda.POR_AUTORIZAR:
            raise CuotaNoPagable("DEUDA_POR_AUTORIZAR")
        if deuda.estado is not EstadoDeuda.REGISTRADA:
            raise CuotaNoPagable("DEUDA_NO_SE_PAGA")
        cuota = deuda.cuota(numero)
        if cuota is None:
            mensaje = "Esa cuota no existe en esta deuda."
            raise PagoInvalido(mensaje, campos={"cuota": mensaje})
        if cuota.pago is not None:
            raise CuotaNoPagable("CUOTA_YA_PAGADA")
        mora = uow.moras.de_la_cuota(deuda.id, numero)
        vigente = mora is not None and mora.estado is not EstadoMora.RECHAZADA
        if proposito is Proposito.PAGO:
            if mora and mora.estado is EstadoMora.POR_APROBAR:
                raise CuotaNoPagable("MORA_POR_APROBAR")
        elif cuota.vence_el >= self._hoy():
            raise CuotaNoPagable("CUOTA_NO_VENCIDA")
        elif vigente:
            raise CuotaNoPagable("MORA_YA_DECLARADA")
        return deuda, cuota

    @staticmethod
    def _visible(uow: UnidadPagos, sesion: SesionActiva, comprobante_id: UUID) -> Comprobante:
        """Lo ven quien lo subió y el gerente del espacio."""
        comprobante = uow.comprobantes.por_id(comprobante_id)
        usuario = sesion.usuario
        if (
            comprobante is None
            or comprobante.gerente_id != espacio_de(sesion)
            or (usuario.rol is not Rol.GERENTE and comprobante.subido_por != usuario.id)
        ):
            raise ComprobanteNoEncontrado()
        return comprobante


class SubirComprobante(_OperacionPagos):
    def __init__(
        self,
        unidad: FabricaUnidadPagos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        zona: ZoneInfo,
        *,
        almacen: Almacen,
        inspector: InspectorArchivos,
        huellero: Huellero,
        cola: ColaComprobantes,
    ) -> None:
        super().__init__(unidad, reloj, publicador, limitador, limite, zona)
        self._almacen = almacen
        self._inspector = inspector
        self._huellero = huellero
        self._cola = cola

    def ejecutar(
        self,
        sesion: SesionActiva,
        deuda_id: UUID | None,
        cuota: int | None,
        contenido: bytes,
        nombre: str | None,
        proposito: Proposito = Proposito.PAGO,
    ) -> Comprobante:
        """El voucher de un pago o, con el propósito mora, la prueba de la mora de la cuota."""
        if deuda_id is None or cuota is None:
            campos = {
                **({"deuda_id": "Indica la deuda que pagaste."} if deuda_id is None else {}),
                **({"cuota": "Indica la cuota que pagaste."} if cuota is None else {}),
            }
            raise CamposFaltantes(campos=campos)
        self._cupo(sesion)
        tipo = validar_archivo(contenido)
        examen = self._inspector.examinar(contenido, tipo)
        gerente_id = espacio_de(sesion)
        with self._unidad() as uow:
            self._sin_bloqueo(uow, sesion)
            # Se comprueba antes de analizar: no se sube el voucher de una cuota que no se paga.
            self._cuota_por_pagar(uow, sesion, deuda_id, cuota, bloquear=False, proposito=proposito)
            comprobante = self._guardar(
                uow, sesion, gerente_id, deuda_id, cuota, contenido, tipo, nombre, examen.paginas
            )
            comprobante.proposito = proposito
            uow.comprobantes.agregar(comprobante)
        try:
            self._cola.encolar(comprobante.id)
        except ErrorCola as error:
            with self._unidad() as uow:
                comprobante.estado = EstadoComprobante.FALLIDO
                uow.comprobantes.guardar(comprobante)
            raise ServicioNoDisponible() from error
        return comprobante

    def _guardar(
        self,
        uow: UnidadPagos,
        sesion: SesionActiva,
        gerente_id: UUID,
        deuda_id: UUID,
        cuota: int,
        contenido: bytes,
        tipo: TipoArchivo,
        nombre: str | None,
        paginas: int,
    ) -> Comprobante:
        comprobante_id = uuid4()
        clave = f"comprobantes/{gerente_id}/{comprobante_id}"
        try:
            self._almacen.guardar(clave, contenido, tipo)
        except ErrorAlmacen as error:
            raise ServicioNoDisponible() from error
        comprobante = Comprobante(
            id=comprobante_id,
            gerente_id=gerente_id,
            subido_por=sesion.usuario.id,
            deuda_id=deuda_id,
            cuota=cuota,
            tipo_archivo=tipo,
            tamano=len(contenido),
            paginas=paginas,
            nombre_archivo=limpiar_nombre(nombre, tipo),
            clave_objeto=clave,
            huella_archivo=huella_archivo(self._huellero, contenido),
            estado=EstadoComprobante.ANALIZANDO,
            subido_en=self._reloj(),
        )
        return comprobante


class AnalizarComprobante:
    """Lo ejecuta el worker. Si se repite para un comprobante ya analizado, no hace nada."""

    def __init__(
        self,
        unidad: FabricaUnidadPagos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        zona: ZoneInfo,
        *,
        almacen: Almacen,
        inspector: InspectorArchivos,
        lector: LectorTexto,
        revisor: RevisorComprobantes,
        huellero: Huellero,
    ) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._publicador = publicador
        self._zona = zona
        self._almacen = almacen
        self._inspector = inspector
        self._lector = lector
        self._revisor = revisor
        self._huellero = huellero

    def ejecutar(self, comprobante_id: UUID) -> EstadoComprobante | None:
        hoy = self._reloj().astimezone(self._zona).date()
        with self._unidad() as uow:
            comprobante = uow.comprobantes.por_id(comprobante_id)
            if comprobante is None or comprobante.estado is not EstadoComprobante.ANALIZANDO:
                return None
            deuda = uow.deudas.por_id(comprobante.deuda_id)
            cuota = deuda.cuota(comprobante.cuota) if deuda else None
            esperada = esperada_de(uow, deuda, cuota, hoy, self._zona) if deuda and cuota else None
            mora = comprobante.proposito is Proposito.MORA
            # Un voucher no respalda dos pagos; una prueba, dos moras.
            usado = uow.comprobantes.prueba_usada if mora else uow.comprobantes.archivo_usado
            repetido = usado(comprobante.gerente_id, comprobante.huella_archivo)
        if esperada is None:
            return self._concluir(comprobante_id, AnalisisComprobante(None), fallido=True)
        if repetido:
            # El mismo archivo: no hace falta leerlo otra vez.
            return self._concluir(comprobante_id, AnalisisComprobante(None, (senal_repetido(),)))
        contenido = self._almacen.leer(comprobante.clave_objeto)
        tipo = comprobante.tipo_archivo
        senales: list[Senal] = evaluar_metadatos(
            self._inspector.examinar(contenido, tipo).metadatos
        )
        lectura = self._lector.leer(contenido, tipo)
        if ilegible := senal_legibilidad(lectura):
            return self._concluir(comprobante_id, AnalisisComprobante(None, (ilegible, *senales)))
        revisar = self._revisor.revisar_prueba_mora if mora else self._revisor.revisar_comprobante
        try:
            revision = revisar(contenido, tipo, lectura)
        except ErrorRevision:
            logger.warning("La revisión con IA del comprobante %s no se completó", comprobante_id)
            return self._concluir(
                comprobante_id, AnalisisComprobante(None, tuple(senales)), None, fallido=True
            )
        if not revision.legible:
            return self._concluir(
                comprobante_id,
                AnalisisComprobante(revision.datos, (senal_ilegible(), *senales)),
            )
        datos = revision.datos
        reglas = evaluar_prueba_mora if mora else evaluar
        senales = [*reglas(datos, lectura, esperada, hoy), *senales]
        if veredicto := senal_veredicto(revision.veredicto, revision.motivos):
            senales.append(veredicto)
        # La operación de una prueba no se reserva: el mismo voucher puede pagar la cuota.
        operacion = None if mora else self._operacion(datos)
        return self._concluir(comprobante_id, AnalisisComprobante(datos, tuple(senales)), operacion)

    def _operacion(self, datos: DatosComprobante) -> bytes | None:
        """La misma operación en otra foto o captura: su número y su fecha."""
        numero = normalizar_numero(datos.numero_operacion)
        if not numero or datos.pagado_el is None:
            return None
        return self._huellero.huella(f"operacion:{numero}|{datos.pagado_el.isoformat()}")

    def _concluir(
        self,
        comprobante_id: UUID,
        analisis: AnalisisComprobante,
        huella_operacion: bytes | None = None,
        *,
        fallido: bool = False,
    ) -> EstadoComprobante | None:
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            comprobante = uow.comprobantes.por_id(comprobante_id, bloquear=True)
            if comprobante is None or comprobante.estado is not EstadoComprobante.ANALIZANDO:
                return None
            if huella_operacion and uow.comprobantes.operacion_usada(
                comprobante.gerente_id, huella_operacion
            ):
                analisis = AnalisisComprobante(analisis.datos, (senal_repetido(),))
            repetido = any(s.codigo == "COMPROBANTE_REPETIDO" for s in analisis.senales)
            if fallido:
                comprobante.estado = EstadoComprobante.FALLIDO
            elif repetido:
                comprobante.estado = EstadoComprobante.REPETIDO
            else:
                comprobante.estado = estado_tras_analisis(analisis)
            comprobante.analisis = analisis
            comprobante.analizado_en = self._reloj()
            comprobante.huella_operacion = huella_operacion
            uow.comprobantes.guardar(comprobante)
            no_corresponde = repetido or (
                comprobante.estado is EstadoComprobante.RECHAZADO
                and cuenta_para_bloqueo(analisis.senales)
            )
            cuenta = uow.cuentas.rol_y_gerente(comprobante.subido_por)
            if no_corresponde and cuenta and cuenta[0] is Rol.ASISTENTE:
                uow.cuentas.bloquear_cuenta(comprobante.subido_por)
                anotar_rechazo(
                    uow,
                    avisos,
                    self._reloj,
                    comprobante.subido_por,
                    comprobante.gerente_id,
                    comprobante.id,
                )
        avisos.enviar()
        return comprobante.estado


class MarcarComprobanteFallido:
    """Cuando el worker agota sus reintentos: el comprobante no queda «analizando» para siempre."""

    def __init__(self, unidad: FabricaUnidadPagos, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, comprobante_id: UUID) -> None:
        with self._unidad() as uow:
            comprobante = uow.comprobantes.por_id(comprobante_id, bloquear=True)
            if comprobante is None or comprobante.estado is not EstadoComprobante.ANALIZANDO:
                return
            comprobante.estado = EstadoComprobante.FALLIDO
            comprobante.analizado_en = self._reloj()
            uow.comprobantes.guardar(comprobante)


@dataclass(frozen=True)
class ComprobanteConsultado:
    comprobante: Comprobante
    # Si quien lo subió tiene el registro de pagos en pausa.
    registro_bloqueado: bool


class ConsultarComprobante(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva, comprobante_id: UUID) -> ComprobanteConsultado:
        with self._unidad() as uow:
            comprobante = self._visible(uow, sesion, comprobante_id)
            bloqueado = uow.bloqueos.vigente(comprobante.subido_por) is not None
            return ComprobanteConsultado(comprobante, bloqueado)


# Qué campo del formulario corrige cada regla que no se cumple con los datos escritos a mano.
CAMPO_DE_SENAL = {
    "MONTO_MENOR": "importe",
    "POSIBLE_MORA": "importe",
    "FECHA_FUTURA": "pagado_el",
    "FECHA_ANTERIOR_A_LA_DEUDA": "pagado_el",
    "CODIGO_DISTINTO": "codigo_pago",
}
LARGO_DATO_A_MANO = 40


@dataclass(frozen=True)
class DatosAMano:
    """Lo que escribe quien subió el voucher cuando la lectura automática falló."""

    importe: str
    pagado_el: date | None
    numero_operacion: str
    lugar: LugarPago | None
    comision: str = ""
    codigo_pago: str | None = None


class CompletarComprobante(_OperacionPagos):
    """Si la lectura automática del voucher falló, quien lo subió escribe sus datos. Pasan por las
    mismas reglas que lo leído (importe, fechas, código y operación repetida) y el voucher queda
    listo marcado como escrito a mano: el pago que respalde llega al gerente con poca confianza.
    Lo que no se cumple se responde como error del formulario; no cuenta para el bloqueo."""

    def __init__(
        self,
        unidad: FabricaUnidadPagos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        zona: ZoneInfo,
        *,
        huellero: Huellero,
    ) -> None:
        super().__init__(unidad, reloj, publicador, limitador, limite, zona)
        self._huellero = huellero

    def ejecutar(
        self, sesion: SesionActiva, comprobante_id: UUID, datos: DatosAMano
    ) -> ComprobanteConsultado:
        campos: dict[str, str] = {}
        if mensaje := error_importe(datos.importe):
            campos["importe"] = mensaje
        if datos.comision.strip() and (mensaje := error_importe(datos.comision)):
            campos["comision"] = mensaje
        if datos.pagado_el is None:
            campos["pagado_el"] = "Escribe la fecha del pago."
        numero = " ".join(datos.numero_operacion.split())
        if not normalizar_numero(numero) or len(numero) > LARGO_DATO_A_MANO:
            campos["numero_operacion"] = "Escribe el número de operación del voucher."
        if datos.lugar is None:
            campos["lugar"] = "Elige dónde pagaste."
        codigo = " ".join((datos.codigo_pago or "").split()) or None
        if codigo and len(codigo) > LARGO_DATO_A_MANO:
            campos["codigo_pago"] = f"Usa como máximo {LARGO_DATO_A_MANO} caracteres."
        if campos:
            raise PagoInvalido(campos=campos)
        assert datos.pagado_el is not None
        self._cupo(sesion)
        hoy = self._hoy()
        leidos = DatosComprobante(
            lugar=datos.lugar,
            codigo_pago=codigo,
            numero_operacion=numero,
            pagado_el=datos.pagado_el,
            moneda=Moneda.SOLES,
            importe=a_importe(datos.importe),
            comision=a_importe(datos.comision) if datos.comision.strip() else None,
        )
        with self._unidad() as uow:
            comprobante = self._visible(uow, sesion, comprobante_id)
            if comprobante.subido_por != sesion.usuario.id:
                raise SinPermiso()
            if (
                comprobante.estado is not EstadoComprobante.FALLIDO
                or comprobante.proposito is not Proposito.PAGO
            ):
                raise ComprobanteNoUsable("COMPROBANTE_NO_SE_COMPLETA")
            deuda, cuota = self._cuota_por_pagar(
                uow, sesion, comprobante.deuda_id, comprobante.cuota, bloquear=False
            )
            esperada = esperada_de(uow, deuda, cuota, hoy, self._zona)
            # Sin texto leído: lo escrito no se puede contrastar con el voucher.
            senales = evaluar(leidos, Lectura("", 0.0, comprobante.paginas), esperada, hoy)
            if graves := [s for s in senales if s.riesgo is Riesgo.ALTO]:
                raise PagoInvalido(
                    graves[0].detalle,
                    campos={CAMPO_DE_SENAL.get(s.codigo, "importe"): s.detalle for s in graves},
                )
            huella = self._huellero.huella(
                f"operacion:{normalizar_numero(numero)}|{datos.pagado_el.isoformat()}"
            )
            if uow.comprobantes.archivo_usado(
                comprobante.gerente_id, comprobante.huella_archivo
            ) or uow.comprobantes.operacion_usada(comprobante.gerente_id, huella):
                raise ComprobanteNoUsable("COMPROBANTE_REPETIDO")
            comprobante.analisis = AnalisisComprobante(leidos, (senal_datos_a_mano(), *senales))
            comprobante.estado = EstadoComprobante.LISTO
            comprobante.huella_operacion = huella
            comprobante.analizado_en = self._reloj()
            uow.comprobantes.guardar(comprobante)
            bloqueado = uow.bloqueos.vigente(comprobante.subido_por) is not None
            return ComprobanteConsultado(comprobante, bloqueado)


@dataclass(frozen=True)
class ContenidoComprobante:
    contenido: bytes
    tipo: TipoArchivo


class LeerComprobante(_OperacionPagos):
    def __init__(
        self,
        unidad: FabricaUnidadPagos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        zona: ZoneInfo,
        *,
        almacen: Almacen,
    ) -> None:
        super().__init__(unidad, reloj, publicador, limitador, limite, zona)
        self._almacen = almacen

    def ejecutar(self, sesion: SesionActiva, comprobante_id: UUID) -> ContenidoComprobante:
        with self._unidad() as uow:
            comprobante = self._visible(uow, sesion, comprobante_id)
        try:
            contenido = self._almacen.leer(comprobante.clave_objeto)
        except ErrorAlmacen as error:
            logger.error("No se pudo leer el archivo del comprobante %s", comprobante_id)
            raise ServicioNoDisponible() from error
        return ContenidoComprobante(contenido, comprobante.tipo_archivo)


@dataclass(frozen=True)
class CuotaPorPagar:
    deuda: Deuda
    cuota: Cuota
    vencida_hace: int | None
    registrada_por: str
    # Por qué el gerente devolvió el último pago de esta cuota, si lo devolvió.
    devuelto_por: str | None = None
    # La mora vigente de la cuota o, si no hay, la última rechazada.
    mora: Mora | None = None
    # El pedido pendiente del gerente para pagarla y a quién se lo hizo.
    pedido: tuple[Pedido, str] | None = None


@dataclass(frozen=True)
class PorPagar:
    # El día de hoy en la zona del espacio: el cliente no decide qué está vencido.
    hoy: date
    cuotas: list[CuotaPorPagar]
    # Si la cuenta tiene el registro de pagos en pausa.
    registro_bloqueado: bool


def _nombre(uow: UnidadPagos, usuario_id: UUID, cache: dict[UUID, str]) -> str:
    if usuario_id not in cache:
        ficha = uow.cuentas.ficha(usuario_id)
        cache[usuario_id] = (
            f"{ficha.datos.nombres} {ficha.datos.apellidos}" if ficha else "Cuenta eliminada"
        )
    return cache[usuario_id]


class ListarPorPagar(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva) -> PorPagar:
        """La próxima cuota sin pagar de cada deuda registrada del espacio, la más atrasada
        primero."""
        hoy = self._hoy()
        with self._unidad() as uow:
            gerente_id = espacio_de(sesion)
            deudas = uow.deudas.por_pagar(gerente_id)
            devueltas = uow.pagos.devoluciones(gerente_id)
            moras = uow.moras.del_espacio_por_cuota(gerente_id)
            pedidos = {(p.deuda_id, p.cuota): p for p in uow.pedidos.pendientes(gerente_id)}
            nombres: dict[UUID, str] = {}
            cuotas = []
            for d in deudas:
                if not d.por_pagar:
                    continue
                clave = (d.id, d.por_pagar[0].numero)
                pedido = pedidos.get(clave)
                cuotas.append(
                    CuotaPorPagar(
                        d,
                        d.por_pagar[0],
                        d.vencida_hace(hoy),
                        _nombre(uow, d.registrada_por, nombres),
                        devueltas.get(clave),
                        moras.get(clave),
                        (pedido, _nombre(uow, pedido.asistente_id, nombres)) if pedido else None,
                    )
                )
            bloqueado = uow.bloqueos.vigente(sesion.usuario.id) is not None
        cuotas.sort(key=lambda c: (c.cuota.vence_el, c.deuda.concepto.casefold()))
        return PorPagar(hoy, cuotas, bloqueado)


@dataclass(frozen=True)
class PagoConDetalle:
    pago: Pago
    concepto: str
    registrado_por: str


# Lo que el gerente puede aceptar sin la verificación automática del voucher. Nunca un voucher que
# ya respalda otro pago, uno repetido o uno que aún se analiza.
OMITIBLES = {
    EstadoComprobante.LISTO,
    EstadoComprobante.RECHAZADO,
    EstadoComprobante.ILEGIBLE,
    EstadoComprobante.FALLIDO,
}
OMITIDA = Comprobacion(
    "verificacion",
    "Verificación del voucher",
    ResultadoComprobacion.AVISO,
    "El gerente registró el pago sin la verificación automática del voucher.",
)


class RegistrarPago(_OperacionPagos):
    def ejecutar(
        self,
        sesion: SesionActiva,
        deuda_id: UUID,
        numero: int,
        comprobante_ids: list[UUID],
        *,
        omitir_verificacion: bool = False,
    ) -> PagoConDetalle:
        """Con `omitir_verificacion`, solo el gerente registra el pago de la cuota aunque el
        sistema no haya aceptado sus vouchers: queda confirmado con confianza 0 y lo dice."""
        ids = list(dict.fromkeys(comprobante_ids))
        if not ids:
            mensaje = "Sube el comprobante del pago."
            raise PagoInvalido(mensaje, campos={"comprobantes": mensaje})
        if len(ids) > MAXIMO_COMPROBANTES:
            mensaje = f"Un pago se registra con hasta {MAXIMO_COMPROBANTES} vouchers."
            raise PagoInvalido(mensaje, campos={"comprobantes": mensaje})
        usuario = sesion.usuario
        gerente = usuario.rol is Rol.GERENTE
        if omitir_verificacion and not gerente:
            raise SinPermiso()
        self._cupo(sesion)
        hoy = self._hoy()
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            self._sin_bloqueo(uow, sesion)
            # Con la deuda tomada, dos registros de la misma cuota van uno tras otro.
            deuda, cuota = self._cuota_por_pagar(uow, sesion, deuda_id, numero, bloquear=True)
            comprobantes = [
                self._usable(uow, sesion, i, deuda.id, numero, omitir=omitir_verificacion)
                for i in ids
            ]
            leidos = [c.datos for c in comprobantes if c.datos]
            esperada = esperada_de(uow, deuda, cuota, hoy, self._zona)
            lista = comprobaciones(
                [(c.datos, c.analisis.senales) for c in comprobantes if c.datos and c.analisis],
                esperada,
            )
            if omitir_verificacion:
                importe, mora = self._sin_verificar(leidos, cuota.importe, esperada.mora)
                lista = (OMITIDA, *lista)
                nivel = 0
            else:
                if len(leidos) != len(comprobantes):
                    raise ComprobanteNoUsable("COMPROBANTE_FALLIDO")
                self._combinan(comprobantes, leidos)
                importe = sum((d.importe or Decimal("0") for d in leidos), Decimal("0"))
                mora = self._suma_la_cuota(importe, cuota.importe, esperada.mora, len(comprobantes))
                nivel = confianza(lista)
            # Una fecha leída que no sirve (futura o ausente) no se usa: vale la de hoy.
            fechas = [d.pagado_el for d in leidos if d.pagado_el and d.pagado_el <= hoy]
            pago = Pago(
                id=uuid4(),
                gerente_id=deuda.gerente_id,
                deuda_id=deuda.id,
                cuota=numero,
                registrado_por=usuario.id,
                importe=importe,
                comision=sum((d.comision or Decimal("0") for d in leidos), Decimal("0")),
                lugar=leidos[0].lugar if leidos else None,
                pagado_el=max(fechas, default=hoy),
                estado=EstadoPago.CONFIRMADO if gerente else EstadoPago.POR_VERIFICAR,
                confianza=nivel,
                comprobaciones=lista,
                registrado_en=self._reloj(),
                comprobantes=tuple(c.id for c in comprobantes),
                mora=mora,
            )
            uow.pagos.agregar(pago)
            uow.comprobantes.vincular(list(pago.comprobantes), pago.id)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.PAGO_REGISTRADO,
                    actor_id=usuario.id,
                    cuenta_id=usuario.id,
                    detalle={
                        "pago_id": str(pago.id),
                        "deuda_id": str(deuda.id),
                        "cuota": numero,
                        "estado": pago.estado.value,
                        "confianza": pago.confianza,
                        "comprobantes": len(pago.comprobantes),
                        "verificacion_omitida": omitir_verificacion,
                    },
                )
            )
            if not gerente:
                avisos.guardar(uow.notificaciones, self._aviso_al_gerente(pago, deuda))
            nombre = _nombre(uow, usuario.id, {})
        avisos.enviar()
        return PagoConDetalle(pago, deuda.concepto, nombre)

    @staticmethod
    def _usable(
        uow: UnidadPagos,
        sesion: SesionActiva,
        comprobante_id: UUID,
        deuda_id: UUID,
        cuota: int,
        *,
        omitir: bool = False,
    ) -> Comprobante:
        comprobante = uow.comprobantes.por_id(comprobante_id, bloquear=True)
        # Solo quien lo subió lo usa.
        if (
            comprobante is None
            or comprobante.gerente_id != espacio_de(sesion)
            or comprobante.subido_por != sesion.usuario.id
        ):
            raise ComprobanteNoEncontrado(campos={"comprobantes": ComprobanteNoEncontrado.mensaje})
        if comprobante.pago_id is not None:
            raise ComprobanteNoUsable("COMPROBANTE_YA_USADO")
        if comprobante.proposito is not Proposito.PAGO:
            raise ComprobanteNoUsable("COMPROBANTE_DE_MORA")
        if (comprobante.deuda_id, comprobante.cuota) != (deuda_id, cuota):
            raise ComprobanteNoUsable("COMPROBANTE_DE_OTRA_CUOTA")
        aceptados = OMITIBLES if omitir else {EstadoComprobante.LISTO}
        if comprobante.estado not in aceptados:
            raise ComprobanteNoUsable(ESTADOS_COMPROBANTE[comprobante.estado])
        return comprobante

    @staticmethod
    def _sin_verificar(
        leidos: list[DatosComprobante], cuota: Decimal, mora: Decimal | None
    ) -> tuple[Decimal, Decimal]:
        """Sin verificación, el pago es la cuota; con la mora aprobada solo si lo leído la suma."""
        leido = sum((d.importe or Decimal("0") for d in leidos), Decimal("0"))
        if mora and leido == cuota + mora:
            return leido, mora
        return cuota, Decimal("0")

    @staticmethod
    def _combinan(comprobantes: list[Comprobante], leidos: list[DatosComprobante]) -> None:
        """Varios vouchers: de un agente, del mismo día y de operaciones distintas."""
        if len(comprobantes) == 1:
            return
        operaciones = [c.huella_operacion for c in comprobantes if c.huella_operacion]
        if (
            any(d.lugar is not LugarPago.AGENTE for d in leidos)
            or len({d.pagado_el for d in leidos}) > 1
            or len(set(operaciones)) != len(operaciones)
        ):
            raise ComprobantesNoCombinan()

    @staticmethod
    def _suma_la_cuota(
        importe: Decimal, cuota: Decimal, mora: Decimal | None, cantidad: int
    ) -> Decimal:
        """Lo pagado es la cuota o, con una mora aprobada, la cuota con la mora. Devuelve lo
        pagado por la mora."""
        if importe == cuota:
            return Decimal("0")
        objetivo = cuota + (mora or Decimal("0"))
        if importe == objetivo:
            return objetivo - cuota
        pagado, esperado = formatear_soles(importe), formatear_soles(objetivo)
        suman = "Los vouchers suman" if cantidad > 1 else "El voucher paga"
        con_mora = " con la mora aprobada" if mora else ""
        if importe < objetivo:
            falta = formatear_soles(objetivo - importe)
            raise ImporteNoCoincide(
                f"{suman} {pagado} y la cuota es {esperado}{con_mora}: falta {falta}. Si el "
                "agente te la cobró por partes, sube los otros vouchers del mismo día."
            )
        raise ImporteNoCoincide(
            f"{suman} {pagado}, más que la cuota de {esperado}{con_mora}. Quita el voucher que no "
            "corresponde a esta cuota."
        )

    @staticmethod
    def _aviso_al_gerente(pago: Pago, deuda: Deuda) -> Notificacion:
        cuota = f" (cuota {pago.cuota} de {len(deuda.cuotas)})" if len(deuda.cuotas) > 1 else ""
        return nueva_notificacion(
            deuda.gerente_id,
            TipoNotificacion.PAGO_POR_VERIFICAR,
            f"pago:{pago.id}:registro",
            "Tu asistente registró un pago",
            f"Pagó «{deuda.concepto}»{cuota} por {formatear_soles(pago.importe)}. Los "
            f"comprobantes respaldan el pago con una confianza de {pago.confianza} %. Revísalo y "
            "confírmalo.",
            pago.registrado_en,
            deuda_id=deuda.id,
            cuenta_id=pago.registrado_por,
        )


class ListarPagos(_OperacionPagos):
    def ejecutar(
        self, sesion: SesionActiva, *, estado: EstadoPago | None = None
    ) -> list[PagoConDetalle]:
        """Los pagos del espacio, los más recientes primero; con `estado`, solo esos."""
        with self._unidad() as uow:
            pagos = uow.pagos.del_espacio(espacio_de(sesion), estado=estado)
            nombres: dict[UUID, str] = {}
            conceptos: dict[UUID, str] = {}
            resultado = []
            for pago in pagos:
                if pago.deuda_id not in conceptos:
                    deuda = uow.deudas.por_id(pago.deuda_id)
                    conceptos[pago.deuda_id] = deuda.concepto if deuda else ""
                resultado.append(
                    PagoConDetalle(
                        pago,
                        conceptos[pago.deuda_id],
                        _nombre(uow, pago.registrado_por, nombres),
                    )
                )
            return resultado


@dataclass(frozen=True)
class PagoConComprobantes:
    detalle: PagoConDetalle
    comprobantes: list[Comprobante]
    cuotas: int


class ConsultarPago(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva, pago_id: UUID) -> PagoConComprobantes:
        """Del espacio: lo ven el gerente y sus asistentes."""
        with self._unidad() as uow:
            pago = uow.pagos.por_id(pago_id)
            if pago is None or pago.gerente_id != espacio_de(sesion):
                raise PagoNoEncontrado()
            deuda = uow.deudas.por_id(pago.deuda_id)
            return PagoConComprobantes(
                PagoConDetalle(
                    pago, deuda.concepto if deuda else "", _nombre(uow, pago.registrado_por, {})
                ),
                uow.comprobantes.del_pago(pago.id),
                len(deuda.cuotas) if deuda else 1,
            )


def _motivo(motivo: str | None) -> str:
    limpio = " ".join((motivo or "").split())
    if not limpio:
        mensaje = "Escribe por qué devuelves este pago: tu asistente lo verá."
        raise PagoInvalido(mensaje, campos={"motivo": mensaje})
    if len(limpio) > LARGO_MOTIVO:
        mensaje = f"Usa como máximo {LARGO_MOTIVO} caracteres."
        raise PagoInvalido(mensaje, campos={"motivo": mensaje})
    return limpio


class _DecisionPago(_OperacionPagos):
    """Solo el gerente decide, con la fila del pago tomada con FOR UPDATE: dos decisiones
    simultáneas no se pisan. Se audita y, si lo registró una asistente, se le avisa."""

    def _decidir(self, sesion: SesionActiva, pago_id: UUID, motivo: str | None) -> Pago:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        self._cupo(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            pago = uow.pagos.por_id(pago_id, bloquear=True)
            if pago is None or pago.gerente_id != sesion.usuario.id:
                raise PagoNoEncontrado()
            ahora = self._reloj()
            if motivo is None:
                pago.confirmar(sesion.usuario.id, ahora)
            else:
                pago.devolver(sesion.usuario.id, ahora, motivo)
            uow.pagos.guardar(pago)
            confirmado = pago.estado is EstadoPago.CONFIRMADO
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.PAGO_CONFIRMADO if confirmado else Accion.PAGO_DEVUELTO,
                    actor_id=sesion.usuario.id,
                    cuenta_id=pago.registrado_por,
                    motivo=pago.motivo_decision,
                    detalle={"pago_id": str(pago.id), "deuda_id": str(pago.deuda_id)},
                )
            )
            deuda = uow.deudas.por_id(pago.deuda_id)
            if pago.registrado_por != sesion.usuario.id and deuda:
                avisos.guardar(uow.notificaciones, self._aviso(pago, deuda.concepto, ahora))
        avisos.enviar()
        return pago

    @staticmethod
    def _aviso(pago: Pago, concepto: str, ahora: datetime) -> Notificacion:
        importe = formatear_soles(pago.importe)
        if pago.estado is EstadoPago.CONFIRMADO:
            return nueva_notificacion(
                pago.registrado_por,
                TipoNotificacion.PAGO_CONFIRMADO,
                f"pago:{pago.id}:confirmado",
                "Tu gerente confirmó un pago",
                f"El pago de «{concepto}» por {importe} quedó confirmado.",
                ahora,
                deuda_id=pago.deuda_id,
            )
        motivo = pago.motivo_decision or ""
        if len(motivo) > LARGO_MOTIVO_EN_AVISO:
            motivo = motivo[: LARGO_MOTIVO_EN_AVISO - 1].rstrip() + "…"
        return nueva_notificacion(
            pago.registrado_por,
            TipoNotificacion.PAGO_DEVUELTO,
            f"pago:{pago.id}:devuelto",
            "Tu gerente devolvió un pago",
            f"Devolvió el pago de «{concepto}» por {importe}: {motivo} La cuota vuelve a estar "
            "por pagar; sube el comprobante correcto.",
            ahora,
            deuda_id=pago.deuda_id,
        )


class ConfirmarPago(_DecisionPago):
    def ejecutar(self, sesion: SesionActiva, pago_id: UUID) -> Pago:
        return self._decidir(sesion, pago_id, None)


class DevolverPago(_DecisionPago):
    def ejecutar(self, sesion: SesionActiva, pago_id: UUID, motivo: str | None) -> Pago:
        return self._decidir(sesion, pago_id, _motivo(motivo))


class _OperacionBloqueosPagos(_OperacionPagos):
    @staticmethod
    def _exigir_gerente(sesion: SesionActiva) -> UUID:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        return sesion.usuario.id


class ListarBloqueosPagos(_OperacionBloqueosPagos):
    def ejecutar(self, sesion: SesionActiva) -> list[Bloqueo]:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            return uow.bloqueos.vigentes_del_espacio(gerente_id)


class LevantarBloqueoPagos(_OperacionBloqueosPagos):
    def ejecutar(self, sesion: SesionActiva, asistente_id: UUID) -> None:
        gerente_id = self._exigir_gerente(sesion)
        self._cupo(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            cuenta = uow.cuentas.rol_y_gerente(asistente_id)
            if cuenta is None or cuenta != (Rol.ASISTENTE, gerente_id):
                raise AsistenteNoEncontrada()
            uow.cuentas.bloquear_cuenta(asistente_id)
            bloqueo = uow.bloqueos.vigente(asistente_id)
            if bloqueo is None:
                raise BloqueoPagosNoEncontrado()
            ahora = self._reloj()
            uow.bloqueos.levantar(bloqueo.id, gerente_id, ahora)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.REGISTRO_PAGOS_DESBLOQUEADO, actor_id=gerente_id, cuenta_id=asistente_id
                )
            )
            avisos.guardar(
                uow.notificaciones,
                nueva_notificacion(
                    asistente_id,
                    TipoNotificacion.REGISTRO_PAGOS_DESBLOQUEADO,
                    f"bloqueo-pagos:{bloqueo.id}:levantado",
                    "Ya puedes registrar pagos",
                    "Tu gerente te permitió registrar pagos otra vez. Sube solo el comprobante de "
                    "la cuota que pagaste.",
                    ahora,
                    cuenta_id=asistente_id,
                ),
            )
        avisos.enviar()


@dataclass(frozen=True)
class MoraConDetalle:
    mora: Mora
    concepto: str
    declarada_por: str
    # El importe de la cuota, sin la mora.
    cuota: Decimal


def _nota(nota: str | None) -> str | None:
    limpia = " ".join((nota or "").split()) or None
    if limpia and len(limpia) > LARGO_MOTIVO:
        mensaje = f"Usa como máximo {LARGO_MOTIVO} caracteres."
        raise PagoInvalido(mensaje, campos={"nota": mensaje})
    return limpia


class DeclararMora(_OperacionPagos):
    """La mora de una cuota vencida, con una prueba ya analizada que subió la misma cuenta. La de
    una asistente espera la aprobación del gerente y la cuota no se paga mientras tanto; la del
    gerente queda aprobada."""

    def ejecutar(
        self,
        sesion: SesionActiva,
        deuda_id: UUID,
        numero: int,
        importe: str,
        prueba_id: UUID,
        nota: str | None = None,
    ) -> MoraConDetalle:
        if mensaje := error_importe(importe):
            raise PagoInvalido(mensaje, campos={"importe": mensaje})
        declarada = a_importe(importe)
        nota_limpia = _nota(nota)
        self._cupo(sesion)
        usuario = sesion.usuario
        gerente = usuario.rol is Rol.GERENTE
        hoy = self._hoy()
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            self._sin_bloqueo(uow, sesion)
            deuda, cuota = self._cuota_por_pagar(
                uow, sesion, deuda_id, numero, bloquear=True, proposito=Proposito.MORA
            )
            prueba = self._prueba(uow, sesion, prueba_id, deuda.id, numero)
            assert prueba.analisis is not None and prueba.datos is not None
            senales = list(prueba.analisis.senales)
            if diferencia := comparar_mora(prueba.datos, cuota.importe, declarada):
                senales.append(diferencia)
            lista = comprobaciones(
                [(prueba.datos, senales)],
                esperada_de(uow, deuda, cuota, hoy, self._zona),
                CRITERIOS_MORA,
            )
            ahora = self._reloj()
            mora = Mora(
                id=uuid4(),
                gerente_id=deuda.gerente_id,
                deuda_id=deuda.id,
                cuota=numero,
                declarada_por=usuario.id,
                importe=declarada,
                prueba_id=prueba.id,
                nota=nota_limpia,
                estado=EstadoMora.APROBADA if gerente else EstadoMora.POR_APROBAR,
                confianza=confianza(lista),
                comprobaciones=lista,
                declarada_en=ahora,
                decidida_por=usuario.id if gerente else None,
                decidida_en=ahora if gerente else None,
            )
            uow.moras.agregar(mora)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.MORA_DECLARADA,
                    actor_id=usuario.id,
                    cuenta_id=usuario.id,
                    detalle={
                        "mora_id": str(mora.id),
                        "deuda_id": str(deuda.id),
                        "cuota": numero,
                        "importe": str(declarada),
                        "estado": mora.estado.value,
                        "confianza": mora.confianza,
                    },
                )
            )
            if not gerente:
                avisos.guardar(
                    uow.notificaciones,
                    nueva_notificacion(
                        deuda.gerente_id,
                        TipoNotificacion.MORA_POR_APROBAR,
                        f"mora:{mora.id}:declarada",
                        "Tu asistente declaró una mora",
                        f"«{deuda.concepto}» venció y la empresa cobra {formatear_soles(declarada)}"
                        f" de mora. La prueba la respalda con una confianza de {mora.confianza} %."
                        " La cuota no se paga hasta que la apruebes o la rechaces.",
                        ahora,
                        deuda_id=deuda.id,
                        cuenta_id=usuario.id,
                    ),
                )
            nombre = _nombre(uow, usuario.id, {})
        avisos.enviar()
        return MoraConDetalle(mora, deuda.concepto, nombre, cuota.importe)

    @staticmethod
    def _prueba(
        uow: UnidadPagos, sesion: SesionActiva, prueba_id: UUID, deuda_id: UUID, cuota: int
    ) -> Comprobante:
        prueba = uow.comprobantes.por_id(prueba_id, bloquear=True)
        if (
            prueba is None
            or prueba.gerente_id != espacio_de(sesion)
            or prueba.subido_por != sesion.usuario.id
        ):
            raise ComprobanteNoEncontrado(campos={"prueba_id": ComprobanteNoEncontrado.mensaje})
        if prueba.proposito is not Proposito.MORA:
            raise ComprobanteNoUsable("COMPROBANTE_DE_PAGO")
        if (prueba.deuda_id, prueba.cuota) != (deuda_id, cuota):
            raise ComprobanteNoUsable("COMPROBANTE_DE_OTRA_CUOTA")
        if prueba.estado is not EstadoComprobante.LISTO:
            raise ComprobanteNoUsable(ESTADOS_COMPROBANTE[prueba.estado])
        return prueba


class _DecisionMora(_OperacionPagos):
    """Solo el gerente aprueba o rechaza, con la fila tomada con FOR UPDATE. Se audita y se avisa
    a quien la declaró."""

    def _decidir(self, sesion: SesionActiva, mora_id: UUID, motivo: str | None) -> Mora:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        self._cupo(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            mora = uow.moras.por_id(mora_id, bloquear=True)
            if mora is None or mora.gerente_id != sesion.usuario.id:
                raise MoraNoEncontrada()
            ahora = self._reloj()
            if motivo is None:
                mora.aprobar(sesion.usuario.id, ahora)
            else:
                mora.rechazar(sesion.usuario.id, ahora, motivo)
            uow.moras.guardar(mora)
            aprobada = mora.estado is EstadoMora.APROBADA
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.MORA_APROBADA if aprobada else Accion.MORA_RECHAZADA,
                    actor_id=sesion.usuario.id,
                    cuenta_id=mora.declarada_por,
                    motivo=mora.motivo_decision,
                    detalle={"mora_id": str(mora.id), "deuda_id": str(mora.deuda_id)},
                )
            )
            deuda = uow.deudas.por_id(mora.deuda_id)
            if mora.declarada_por != sesion.usuario.id and deuda:
                avisos.guardar(uow.notificaciones, self._aviso(mora, deuda.concepto, ahora))
        avisos.enviar()
        return mora

    @staticmethod
    def _aviso(mora: Mora, concepto: str, ahora: datetime) -> Notificacion:
        importe = formatear_soles(mora.importe)
        if mora.estado is EstadoMora.APROBADA:
            tipo, titulo = TipoNotificacion.MORA_APROBADA, "Tu gerente aprobó la mora"
            cuerpo = (
                f"La mora de {importe} de «{concepto}» quedó aprobada: ya puedes pagar la cuota "
                "con la mora."
            )
        else:
            tipo, titulo = TipoNotificacion.MORA_RECHAZADA, "Tu gerente rechazó la mora"
            cuerpo = (
                f"Rechazó la mora de {importe} de «{concepto}»: {mora.motivo_decision} La cuota "
                "se paga sin la mora."
            )
        return nueva_notificacion(
            mora.declarada_por,
            tipo,
            f"mora:{mora.id}:{mora.estado.value}",
            titulo,
            cuerpo,
            ahora,
            deuda_id=mora.deuda_id,
        )


class AprobarMora(_DecisionMora):
    def ejecutar(self, sesion: SesionActiva, mora_id: UUID) -> Mora:
        return self._decidir(sesion, mora_id, None)


class RechazarMora(_DecisionMora):
    def ejecutar(self, sesion: SesionActiva, mora_id: UUID, motivo: str | None) -> Mora:
        limpio = " ".join((motivo or "").split())
        if not limpio:
            mensaje = "Escribe por qué rechazas esta mora: tu asistente lo verá."
            raise PagoInvalido(mensaje, campos={"motivo": mensaje})
        if len(limpio) > LARGO_MOTIVO:
            mensaje = f"Usa como máximo {LARGO_MOTIVO} caracteres."
            raise PagoInvalido(mensaje, campos={"motivo": mensaje})
        return self._decidir(sesion, mora_id, limpio)


def _con_detalle(uow: UnidadPagos, mora: Mora, nombres: dict[UUID, str]) -> MoraConDetalle:
    deuda = uow.deudas.por_id(mora.deuda_id)
    cuota = deuda.cuota(mora.cuota) if deuda else None
    return MoraConDetalle(
        mora,
        deuda.concepto if deuda else "",
        _nombre(uow, mora.declarada_por, nombres),
        cuota.importe if cuota else Decimal("0"),
    )


class ListarMoras(_OperacionPagos):
    def ejecutar(
        self, sesion: SesionActiva, *, estado: EstadoMora | None = None
    ) -> list[MoraConDetalle]:
        """Las del espacio, las más recientes primero; con `estado`, solo esas."""
        with self._unidad() as uow:
            nombres: dict[UUID, str] = {}
            return [
                _con_detalle(uow, m, nombres)
                for m in uow.moras.del_espacio(espacio_de(sesion), estado=estado)
            ]


@dataclass(frozen=True)
class MoraConPrueba:
    detalle: MoraConDetalle
    prueba: Comprobante | None


class ConsultarMora(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva, mora_id: UUID) -> MoraConPrueba:
        with self._unidad() as uow:
            mora = uow.moras.por_id(mora_id)
            if mora is None or mora.gerente_id != espacio_de(sesion):
                raise MoraNoEncontrada()
            return MoraConPrueba(
                _con_detalle(uow, mora, {}), uow.comprobantes.por_id(mora.prueba_id)
            )


LARGO_NOTA_PEDIDO = 500


@dataclass(frozen=True)
class PedidoConDetalle:
    pedido: Pedido
    concepto: str
    cuota: Cuota
    cuotas: int
    vencida_hace: int | None
    asistente: str


class PedirPago(_OperacionPagos):
    """El gerente pide a una asistente activa de su espacio que pague una cuota registrada que
    falta pagar. Le llega un aviso que reaparece mientras la cuota siga por pagar."""

    def ejecutar(
        self,
        sesion: SesionActiva,
        deuda_id: UUID,
        numero: int,
        asistente_id: UUID,
        nota: str | None = None,
    ) -> PedidoConDetalle:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        limpia = " ".join((nota or "").split()) or None
        if limpia and len(limpia) > LARGO_NOTA_PEDIDO:
            mensaje = f"Usa como máximo {LARGO_NOTA_PEDIDO} caracteres."
            raise PagoInvalido(mensaje, campos={"nota": mensaje})
        self._cupo(sesion)
        hoy = self._hoy()
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            deuda, cuota = self._cuota_por_pagar(uow, sesion, deuda_id, numero, bloquear=True)
            if not uow.pedidos.asistente_activa(sesion.usuario.id, asistente_id):
                raise AsistenteNoEncontrada()
            ahora = self._reloj()
            pedido = Pedido(
                uuid4(), deuda.gerente_id, deuda.id, numero, asistente_id, limpia, ahora
            )
            uow.pedidos.agregar(pedido)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.PAGO_PEDIDO,
                    actor_id=sesion.usuario.id,
                    cuenta_id=asistente_id,
                    detalle={"pedido_id": str(pedido.id), "deuda_id": str(deuda.id)},
                )
            )
            importe = formatear_soles(cuota.importe)
            avisos.guardar(
                uow.notificaciones,
                nueva_notificacion(
                    asistente_id,
                    TipoNotificacion.PAGO_PEDIDO,
                    f"pedido:{pedido.id}",
                    "Tu gerente te pidió pagar una deuda",
                    f"«{deuda.concepto}» por {importe}, vence el "
                    f"{formatear_fecha(cuota.vence_el)}."
                    + (f" Nota: {limpia}" if limpia else "")
                    + " Te lo recordaremos hasta que registres el pago.",
                    ahora,
                    deuda_id=deuda.id,
                ),
            )
            detalle = PedidoConDetalle(
                pedido,
                deuda.concepto,
                cuota,
                len(deuda.cuotas),
                deuda.vencida_hace(hoy),
                _nombre(uow, asistente_id, {}),
            )
        avisos.enviar()
        return detalle


class RetirarPedido(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva, pedido_id: UUID) -> None:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        self._cupo(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            pedido = uow.pedidos.por_id(pedido_id, bloquear=True)
            if pedido is None or pedido.gerente_id != sesion.usuario.id:
                raise PedidoNoEncontrado()
            ahora = self._reloj()
            pedido.retirar(sesion.usuario.id, ahora)
            uow.pedidos.guardar(pedido)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.PEDIDO_RETIRADO,
                    actor_id=sesion.usuario.id,
                    cuenta_id=pedido.asistente_id,
                    detalle={"pedido_id": str(pedido.id), "deuda_id": str(pedido.deuda_id)},
                )
            )
            deuda = uow.deudas.por_id(pedido.deuda_id)
            avisos.guardar(
                uow.notificaciones,
                nueva_notificacion(
                    pedido.asistente_id,
                    TipoNotificacion.PEDIDO_RETIRADO,
                    f"pedido:{pedido.id}:retirado",
                    "Tu gerente retiró un pedido de pago",
                    f"Ya no te pide pagar «{deuda.concepto if deuda else ''}». Sigue en lo que "
                    "falta pagar, sin prioridad.",
                    ahora,
                    deuda_id=pedido.deuda_id,
                ),
            )
        avisos.enviar()


class ListarPedidos(_OperacionPagos):
    def ejecutar(self, sesion: SesionActiva) -> list[PedidoConDetalle]:
        """Los pendientes: a una asistente, los suyos; al gerente, los de su espacio."""
        hoy = self._hoy()
        usuario = sesion.usuario
        with self._unidad() as uow:
            pedidos = uow.pedidos.pendientes(
                espacio_de(sesion), None if usuario.rol is Rol.GERENTE else usuario.id
            )
            nombres: dict[UUID, str] = {}
            resultado = []
            for pedido in pedidos:
                deuda = uow.deudas.por_id(pedido.deuda_id)
                cuota = deuda.cuota(pedido.cuota) if deuda else None
                if deuda is None or cuota is None:
                    continue
                resultado.append(
                    PedidoConDetalle(
                        pedido,
                        deuda.concepto,
                        cuota,
                        len(deuda.cuotas),
                        deuda.vencida_hace(hoy),
                        _nombre(uow, pedido.asistente_id, nombres),
                    )
                )
            return resultado
