"""Casos de uso de las deudas.

Registrar: el gerente y sus asistentes registran deudas en el espacio del gerente (sale de la
sesión). Cada deuda nace de un documento propio, ya analizado y listo, que no respalda otra deuda.
El backend vuelve a validar todo lo que llega del formulario y aplica las reglas del espacio con
lo que dice el documento. Lo que registra una asistente se notifica al gerente.

Decidir: solo el gerente autoriza, rechaza, da su visto bueno o anula, con la fila de la deuda
tomada con FOR UPDATE para que dos decisiones simultáneas no se pisen. Cada paso queda en la
auditoría y, si la registró una asistente, se le notifica.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import exigir_cupo
from app.acceso.dominio.errores import SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite, Reloj
from app.categorias.aplicacion.categorias import espacio_de
from app.deudas.dominio.errores import (
    CategoriaNoDisponible,
    DeudaInvalida,
    DeudaNoEncontrada,
    DocumentoNoRegistrable,
)
from app.deudas.dominio.modelos import Deuda, EstadoDeuda, MotivoEspera
from app.deudas.dominio.puertos import FabricaUnidadDeudas, UnidadDeudas
from app.deudas.dominio.registro import (
    CuotaEnviada,
    DatosDeuda,
    campos_corregidos,
    evaluar_registro,
)
from app.documentos.dominio.errores import DocumentoNoEncontrado, RegistroBloqueado
from app.documentos.dominio.modelos import Documento, EstadoDocumento, TipoDocumento
from app.notificaciones.aplicacion.notificaciones import Avisos
from app.notificaciones.dominio.modelos import (
    Notificacion,
    TipoNotificacion,
    nueva_notificacion,
)
from app.notificaciones.dominio.puertos import PublicadorAvisos
from app.reglas.aplicacion.reglas import identidades
from app.reglas.dominio.importes import formatear_soles

MESES = "ene feb mar abr may jun jul ago set oct nov dic".split()
LARGO_MOTIVO = 500
LARGO_MOTIVO_EN_AVISO = 280

POR_QUE_ESPERA = {
    MotivoEspera.IMPORTE_SOBRE_LIMITE: "supera tu límite",
    MotivoEspera.TITULAR_DISTINTO: "el titular no eres tú ni un titular autorizado",
    MotivoEspera.DOCUMENTO_DUDOSO: "el documento tiene señales que conviene revisar",
    MotivoEspera.DATOS_CORREGIDOS: "se corrigió a mano el importe o el código de pago",
}

ESTADOS_DOCUMENTO = {
    EstadoDocumento.ANALIZANDO: "DOCUMENTO_EN_ANALISIS",
    EstadoDocumento.ILEGIBLE: "DOCUMENTO_ILEGIBLE",
    EstadoDocumento.REPETIDO: "DOCUMENTO_REPETIDO",
    EstadoDocumento.RECHAZADO: "DOCUMENTO_RECHAZADO",
    EstadoDocumento.FALLIDO: "DOCUMENTO_FALLIDO",
}


def formatear_fecha(fecha: date) -> str:
    return f"{fecha.day} {MESES[fecha.month - 1]} {fecha.year}"


def _recortar(texto: str, largo: int) -> str:
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


@dataclass(frozen=True)
class NuevaDeuda:
    documento_id: UUID
    concepto: str
    lugar_pago: str | None
    cuotas: list[CuotaEnviada]
    categoria_id: UUID | None = None
    titular_nombre: str | None = None
    titular_tipo_documento: str | None = None
    titular_numero_documento: str | None = None
    codigo_pago: str | None = None


@dataclass(frozen=True)
class DeudaRegistrada:
    deuda: Deuda
    # Lo que se le advierte al gerente cuando la registra él mismo.
    avisos: tuple[str, ...]


@dataclass(frozen=True)
class DeudaConDetalle:
    deuda: Deuda
    documento: Documento | None
    registrada_por: str


class _OperacionDeudas:
    def __init__(
        self,
        unidad: FabricaUnidadDeudas,
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

    def _exigir_gerente(self, sesion: SesionActiva) -> UUID:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        exigir_cupo(self._limitador, (self._limite, str(sesion.usuario.id)))
        return sesion.usuario.id

    @staticmethod
    def _deuda(
        uow: UnidadDeudas, sesion: SesionActiva, deuda_id: UUID, *, bloquear: bool = False
    ) -> Deuda:
        """Del espacio de la sesión; una asistente solo ve las que registró."""
        deuda = uow.deudas.por_id(deuda_id, bloquear=bloquear)
        usuario = sesion.usuario
        if (
            deuda is None
            or deuda.gerente_id != espacio_de(sesion)
            or (usuario.rol is not Rol.GERENTE and deuda.registrada_por != usuario.id)
        ):
            raise DeudaNoEncontrada()
        return deuda

    @staticmethod
    def _auditar(
        uow: UnidadDeudas,
        accion: Accion,
        sesion: SesionActiva,
        deuda: Deuda,
        motivo: str | None = None,
        **detalle: object,
    ) -> None:
        uow.auditoria.registrar(
            EventoAuditoria(
                accion,
                actor_id=sesion.usuario.id,
                cuenta_id=deuda.registrada_por,
                motivo=motivo,
                detalle={"deuda_id": str(deuda.id), "estado": deuda.estado.value, **detalle},
            )
        )


class RegistrarDeuda(_OperacionDeudas):
    def ejecutar(self, sesion: SesionActiva, nueva: NuevaDeuda) -> DeudaRegistrada:
        usuario = sesion.usuario
        gerente_id = espacio_de(sesion)
        exigir_cupo(self._limitador, (self._limite, str(usuario.id)))
        datos = DatosDeuda.crear(
            concepto=nueva.concepto,
            lugar_pago=nueva.lugar_pago,
            cuotas=nueva.cuotas,
            titular_nombre=nueva.titular_nombre,
            titular_tipo_documento=nueva.titular_tipo_documento,
            titular_numero_documento=nueva.titular_numero_documento,
            codigo_pago=nueva.codigo_pago,
            hoy=self._hoy(),
        )
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            # Una tras otra por cuenta: el bloqueo y el documento se comprueban sin carreras.
            uow.cuentas.bloquear_cuenta(usuario.id)
            if usuario.rol is Rol.ASISTENTE and (bloqueo := uow.bloqueos.vigente(usuario.id)):
                raise RegistroBloqueado(bloqueo.bloqueado_en)
            documento = self._documento(uow, sesion, gerente_id, nueva.documento_id)
            if nueva.categoria_id is not None:
                categoria = uow.categorias.por_id(gerente_id, nueva.categoria_id)
                if categoria is None or categoria.archivada:
                    raise CategoriaNoDisponible()
            regla = uow.reglas.regla(gerente_id)
            leidos = documento.analisis.datos if documento.analisis else None
            corregidos = campos_corregidos(datos, leidos)
            resultado = evaluar_registro(
                registra=usuario.rol,
                datos=datos,
                analisis=documento.analisis,
                limite=regla.limite_importe if regla else None,
                identidades=identidades(uow, gerente_id),
                corregidos=corregidos,
            )
            asistente = usuario.rol is Rol.ASISTENTE
            deuda = Deuda(
                id=uuid4(),
                gerente_id=gerente_id,
                registrada_por=usuario.id,
                documento_id=documento.id,
                concepto=datos.concepto,
                categoria_id=nueva.categoria_id,
                tipo_documento=documento.tipo_documento or TipoDocumento.OTRO,
                cuotas=datos.cuotas,
                lugar_pago=datos.lugar_pago,
                titular_nombre=datos.titular_nombre,
                titular_documento=datos.titular_documento,
                codigo_pago=datos.codigo_pago,
                estado=EstadoDeuda.POR_AUTORIZAR if resultado.motivos else EstadoDeuda.REGISTRADA,
                creado_en=self._reloj(),
                motivos=resultado.motivos,
                revision_pendiente=asistente and not resultado.motivos,
                campos_corregidos=corregidos,
            )
            uow.deudas.agregar(deuda)
            self._auditar(
                uow,
                Accion.DEUDA_REGISTRADA,
                sesion,
                deuda,
                motivos=[m.value for m in deuda.motivos],
                campos_corregidos=list(corregidos),
                cuotas=len(deuda.cuotas),
            )
            if asistente:
                avisos.guardar(uow.notificaciones, self._aviso_al_gerente(deuda))
        avisos.enviar()
        return DeudaRegistrada(deuda, resultado.avisos)

    @staticmethod
    def _documento(
        uow: UnidadDeudas, sesion: SesionActiva, gerente_id: UUID, documento_id: UUID
    ) -> Documento:
        documento = uow.documentos.por_id(documento_id, bloquear=True)
        # Solo quien subió el documento lo registra.
        if (
            documento is None
            or documento.gerente_id != gerente_id
            or documento.subido_por != sesion.usuario.id
        ):
            raise DocumentoNoEncontrado()
        if documento.deuda_id is not None:
            raise DocumentoNoRegistrable("DOCUMENTO_YA_USADO")
        if documento.estado is not EstadoDocumento.LISTO:
            raise DocumentoNoRegistrable(ESTADOS_DOCUMENTO[documento.estado])
        return documento

    @staticmethod
    def _aviso_al_gerente(deuda: Deuda) -> Notificacion:
        importe = formatear_soles(deuda.importe)
        if deuda.estado is EstadoDeuda.POR_AUTORIZAR:
            razones = ", ".join(POR_QUE_ESPERA[m] for m in deuda.motivos)
            return nueva_notificacion(
                deuda.gerente_id,
                TipoNotificacion.DEUDA_POR_AUTORIZAR,
                f"deuda:{deuda.id}:registro",
                "Una deuda espera tu autorización",
                f"Tu asistente registró «{deuda.concepto}» por {importe}. No se pagará hasta que "
                f"la autorices: {razones}.",
                deuda.creado_en,
                deuda_id=deuda.id,
                cuenta_id=deuda.registrada_por,
            )
        return nueva_notificacion(
            deuda.gerente_id,
            TipoNotificacion.DEUDA_REGISTRADA,
            f"deuda:{deuda.id}:registro",
            "Tu asistente registró una deuda",
            f"«{deuda.concepto}» por {importe}, vence el {formatear_fecha(deuda.vence_el)}. Ya se "
            "puede pagar; revísala cuando puedas y anúlala si no corresponde.",
            deuda.creado_en,
            deuda_id=deuda.id,
            cuenta_id=deuda.registrada_por,
        )


class ListarDeudas(_OperacionDeudas):
    def ejecutar(self, sesion: SesionActiva, *, solo_pendientes: bool) -> list[DeudaConDetalle]:
        """El gerente ve las de su espacio (o solo sus pendientes); una asistente, las suyas."""
        with self._unidad() as uow:
            if sesion.usuario.rol is Rol.GERENTE:
                deudas = uow.deudas.del_espacio(sesion.usuario.id, solo_pendientes=solo_pendientes)
            else:
                deudas = uow.deudas.registradas_por(sesion.usuario.id)
            nombres: dict[UUID, str] = {}
            return [
                DeudaConDetalle(d, None, _nombre(uow, d.registrada_por, nombres)) for d in deudas
            ]


def _nombre(uow: UnidadDeudas, usuario_id: UUID, cache: dict[UUID, str]) -> str:
    if usuario_id not in cache:
        ficha = uow.cuentas.ficha(usuario_id)
        cache[usuario_id] = (
            f"{ficha.datos.nombres} {ficha.datos.apellidos}" if ficha else "Cuenta eliminada"
        )
    return cache[usuario_id]


class ConsultarDeuda(_OperacionDeudas):
    def ejecutar(self, sesion: SesionActiva, deuda_id: UUID) -> DeudaConDetalle:
        with self._unidad() as uow:
            deuda = self._deuda(uow, sesion, deuda_id)
            documento = uow.documentos.por_id(deuda.documento_id)
            return DeudaConDetalle(deuda, documento, _nombre(uow, deuda.registrada_por, {}))


def _motivo_obligatorio(motivo: str | None, accion: str) -> str:
    limpio = " ".join((motivo or "").split())
    if not limpio:
        mensaje = f"Escribe por qué {accion} esta deuda: tu asistente lo verá."
        raise DeudaInvalida(mensaje, campos={"motivo": mensaje})
    if len(limpio) > LARGO_MOTIVO:
        mensaje = f"Usa como máximo {LARGO_MOTIVO} caracteres."
        raise DeudaInvalida(mensaje, campos={"motivo": mensaje})
    return limpio


class _DecisionDeuda(_OperacionDeudas):
    accion: Accion

    def _notificar(
        self, uow: UnidadDeudas, avisos: Avisos, deuda: Deuda, sesion: SesionActiva
    ) -> None:
        """Si la registró una asistente, se le avisa la decisión."""

    def _aplicar(self, deuda: Deuda, sesion: SesionActiva, motivo: str | None) -> None:
        raise NotImplementedError

    def _decidir(self, sesion: SesionActiva, deuda_id: UUID, motivo: str | None) -> Deuda:
        self._exigir_gerente(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            deuda = self._deuda(uow, sesion, deuda_id, bloquear=True)
            self._aplicar(deuda, sesion, motivo)
            uow.deudas.guardar(deuda)
            self._auditar(uow, self.accion, sesion, deuda, deuda.motivo_decision)
            if deuda.registrada_por != sesion.usuario.id:
                self._notificar(uow, avisos, deuda, sesion)
        avisos.enviar()
        return deuda

    @staticmethod
    def _aviso(
        uow: UnidadDeudas,
        avisos: Avisos,
        deuda: Deuda,
        tipo: TipoNotificacion,
        titulo: str,
        cuerpo: str,
    ) -> None:
        assert deuda.decidida_en is not None
        avisos.guardar(
            uow.notificaciones,
            nueva_notificacion(
                deuda.registrada_por,
                tipo,
                f"deuda:{deuda.id}:{tipo.value.lower()}",
                titulo,
                cuerpo,
                deuda.decidida_en,
                deuda_id=deuda.id,
            ),
        )


class AutorizarDeuda(_DecisionDeuda):
    accion = Accion.DEUDA_AUTORIZADA

    def ejecutar(self, sesion: SesionActiva, deuda_id: UUID) -> Deuda:
        return self._decidir(sesion, deuda_id, None)

    def _aplicar(self, deuda: Deuda, sesion: SesionActiva, motivo: str | None) -> None:
        deuda.autorizar(sesion.usuario.id, self._reloj())

    def _notificar(
        self, uow: UnidadDeudas, avisos: Avisos, deuda: Deuda, sesion: SesionActiva
    ) -> None:
        self._aviso(
            uow,
            avisos,
            deuda,
            TipoNotificacion.DEUDA_AUTORIZADA,
            "Tu gerente autorizó una deuda",
            f"«{deuda.concepto}» por {formatear_soles(deuda.importe)} ya se puede pagar.",
        )


class RechazarDeuda(_DecisionDeuda):
    accion = Accion.DEUDA_RECHAZADA

    def ejecutar(self, sesion: SesionActiva, deuda_id: UUID, motivo: str | None) -> Deuda:
        return self._decidir(sesion, deuda_id, _motivo_obligatorio(motivo, "rechazas"))

    def _aplicar(self, deuda: Deuda, sesion: SesionActiva, motivo: str | None) -> None:
        assert motivo is not None
        deuda.rechazar(sesion.usuario.id, self._reloj(), motivo)

    def _notificar(
        self, uow: UnidadDeudas, avisos: Avisos, deuda: Deuda, sesion: SesionActiva
    ) -> None:
        motivo = _recortar(deuda.motivo_decision or "", LARGO_MOTIVO_EN_AVISO)
        self._aviso(
            uow,
            avisos,
            deuda,
            TipoNotificacion.DEUDA_RECHAZADA,
            "Tu gerente rechazó una deuda",
            f"«{deuda.concepto}» no se pagará. Motivo: {motivo}",
        )


class DarVistoBueno(_DecisionDeuda):
    accion = Accion.DEUDA_REVISADA

    def ejecutar(self, sesion: SesionActiva, deuda_id: UUID) -> Deuda:
        return self._decidir(sesion, deuda_id, None)

    def _aplicar(self, deuda: Deuda, sesion: SesionActiva, motivo: str | None) -> None:
        deuda.dar_visto_bueno(sesion.usuario.id, self._reloj())


class AnularDeuda(_DecisionDeuda):
    accion = Accion.DEUDA_ANULADA

    def ejecutar(self, sesion: SesionActiva, deuda_id: UUID, motivo: str | None) -> Deuda:
        return self._decidir(sesion, deuda_id, _motivo_obligatorio(motivo, "anulas"))

    def _aplicar(self, deuda: Deuda, sesion: SesionActiva, motivo: str | None) -> None:
        assert motivo is not None
        deuda.anular(sesion.usuario.id, self._reloj(), motivo)

    def _notificar(
        self, uow: UnidadDeudas, avisos: Avisos, deuda: Deuda, sesion: SesionActiva
    ) -> None:
        motivo = _recortar(deuda.motivo_decision or "", LARGO_MOTIVO_EN_AVISO)
        self._aviso(
            uow,
            avisos,
            deuda,
            TipoNotificacion.DEUDA_ANULADA,
            "Tu gerente anuló una deuda",
            f"«{deuda.concepto}» ya no se pagará. Motivo: {motivo}",
        )
