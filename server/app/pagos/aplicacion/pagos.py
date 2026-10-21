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
from app.deudas.dominio.errores import DeudaNoEncontrada
from app.deudas.dominio.modelos import Cuota, Deuda, EstadoDeuda, EstadoPago, LugarPago
from app.documentos.aplicacion.documentos import huella_archivo
from app.documentos.dominio.analisis import evaluar_metadatos, normalizar_numero, senal_veredicto
from app.documentos.dominio.archivos import limpiar_nombre, validar_archivo
from app.documentos.dominio.bloqueos import Bloqueo, contar_desde
from app.documentos.dominio.errores import AsistenteNoEncontrada
from app.documentos.dominio.modelos import Senal, TipoArchivo
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
from app.pagos.dominio.confianza import comprobaciones, confianza
from app.pagos.dominio.errores import (
    BloqueoPagosNoEncontrado,
    CamposFaltantes,
    ComprobanteNoEncontrado,
    ComprobanteNoUsable,
    ComprobantesNoCombinan,
    CuotaNoPagable,
    ImporteNoCoincide,
    PagoInvalido,
    PagoNoEncontrado,
    RegistroPagosBloqueado,
)
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    Comprobante,
    DatosComprobante,
    EstadoComprobante,
    Pago,
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
    cuenta_para_bloqueo,
    estado_tras_analisis,
    evaluar,
    senal_ilegible,
    senal_legibilidad,
    senal_repetido,
)
from app.reglas.dominio.importes import formatear_soles

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
    return CuotaEsperada(
        importe=cuota.importe,
        codigo_pago=deuda.codigo_pago,
        empresa=leidos.emisor if leidos else None,
        titular=deuda.titular_nombre,
        lugares=deuda.lugares_pago,
        registrada_el=deuda.creado_en.astimezone(zona).date(),
        vencida=cuota.vence_el < hoy,
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

    @staticmethod
    def _cuota_por_pagar(
        uow: UnidadPagos, sesion: SesionActiva, deuda_id: UUID, numero: int, *, bloquear: bool
    ) -> tuple[Deuda, Cuota]:
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
    ) -> Comprobante:
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
            self._cuota_por_pagar(uow, sesion, deuda_id, cuota, bloquear=False)
            comprobante = self._guardar(
                uow, sesion, gerente_id, deuda_id, cuota, contenido, tipo, nombre, examen.paginas
            )
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
        uow.comprobantes.agregar(comprobante)
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
            repetido = uow.comprobantes.archivo_usado(
                comprobante.gerente_id, comprobante.huella_archivo
            )
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
        try:
            revision = self._revisor.revisar_comprobante(contenido, tipo, lectura)
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
        senales = [*evaluar(datos, lectura, esperada, hoy), *senales]
        if veredicto := senal_veredicto(revision.veredicto, revision.motivos):
            senales.append(veredicto)
        return self._concluir(
            comprobante_id, AnalisisComprobante(datos, tuple(senales)), self._operacion(datos)
        )

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
            nombres: dict[UUID, str] = {}
            cuotas = [
                CuotaPorPagar(
                    d,
                    d.por_pagar[0],
                    d.vencida_hace(hoy),
                    _nombre(uow, d.registrada_por, nombres),
                    devueltas.get((d.id, d.por_pagar[0].numero)),
                )
                for d in deudas
                if d.por_pagar
            ]
            bloqueado = uow.bloqueos.vigente(sesion.usuario.id) is not None
        cuotas.sort(key=lambda c: (c.cuota.vence_el, c.deuda.concepto.casefold()))
        return PorPagar(hoy, cuotas, bloqueado)


@dataclass(frozen=True)
class PagoConDetalle:
    pago: Pago
    concepto: str
    registrado_por: str


class RegistrarPago(_OperacionPagos):
    def ejecutar(
        self, sesion: SesionActiva, deuda_id: UUID, numero: int, comprobante_ids: list[UUID]
    ) -> PagoConDetalle:
        ids = list(dict.fromkeys(comprobante_ids))
        if not ids:
            mensaje = "Sube el comprobante del pago."
            raise PagoInvalido(mensaje, campos={"comprobantes": mensaje})
        if len(ids) > MAXIMO_COMPROBANTES:
            mensaje = f"Un pago se registra con hasta {MAXIMO_COMPROBANTES} vouchers."
            raise PagoInvalido(mensaje, campos={"comprobantes": mensaje})
        self._cupo(sesion)
        usuario = sesion.usuario
        hoy = self._hoy()
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            self._sin_bloqueo(uow, sesion)
            # Con la deuda tomada, dos registros de la misma cuota van uno tras otro.
            deuda, cuota = self._cuota_por_pagar(uow, sesion, deuda_id, numero, bloquear=True)
            comprobantes = [self._usable(uow, sesion, i, deuda.id, numero) for i in ids]
            leidos = [c.datos for c in comprobantes if c.datos]
            if len(leidos) != len(comprobantes):
                raise ComprobanteNoUsable("COMPROBANTE_FALLIDO")
            self._combinan(comprobantes, leidos)
            importe = sum((d.importe or Decimal("0") for d in leidos), Decimal("0"))
            self._suma_la_cuota(importe, cuota.importe, len(comprobantes))
            esperada = esperada_de(uow, deuda, cuota, hoy, self._zona)
            lista = comprobaciones(
                [(c.datos, c.analisis.senales) for c in comprobantes if c.datos and c.analisis],
                esperada,
            )
            gerente = usuario.rol is Rol.GERENTE
            pago = Pago(
                id=uuid4(),
                gerente_id=deuda.gerente_id,
                deuda_id=deuda.id,
                cuota=numero,
                registrado_por=usuario.id,
                importe=importe,
                comision=sum((d.comision or Decimal("0") for d in leidos), Decimal("0")),
                lugar=leidos[0].lugar,
                pagado_el=max(d.pagado_el for d in leidos if d.pagado_el),
                estado=EstadoPago.CONFIRMADO if gerente else EstadoPago.POR_VERIFICAR,
                confianza=confianza(lista),
                comprobaciones=lista,
                registrado_en=self._reloj(),
                comprobantes=tuple(c.id for c in comprobantes),
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
        uow: UnidadPagos, sesion: SesionActiva, comprobante_id: UUID, deuda_id: UUID, cuota: int
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
        if (comprobante.deuda_id, comprobante.cuota) != (deuda_id, cuota):
            raise ComprobanteNoUsable("COMPROBANTE_DE_OTRA_CUOTA")
        if comprobante.estado is not EstadoComprobante.LISTO:
            raise ComprobanteNoUsable(ESTADOS_COMPROBANTE[comprobante.estado])
        return comprobante

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
    def _suma_la_cuota(importe: Decimal, cuota: Decimal, cantidad: int) -> None:
        if importe == cuota:
            return
        pagado, esperado = formatear_soles(importe), formatear_soles(cuota)
        if importe < cuota:
            falta = formatear_soles(cuota - importe)
            raise ImporteNoCoincide(
                f"{'Los vouchers suman' if cantidad > 1 else 'El voucher paga'} {pagado} y la "
                f"cuota es {esperado}: falta {falta}. Si el agente te la cobró por partes, sube "
                "los otros vouchers del mismo día."
            )
        raise ImporteNoCoincide(
            f"{'Los vouchers suman' if cantidad > 1 else 'El voucher paga'} {pagado}, más que la "
            f"cuota de {esperado}. Quita el voucher que no corresponde a esta cuota."
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
