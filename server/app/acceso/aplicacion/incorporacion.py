from collections.abc import Mapping
from dataclasses import replace

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.aplicacion.pasos import pasos_de
from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import DatosYaConfirmados, IncorporacionPendiente, NoAutenticado
from app.acceso.dominio.incorporacion import (
    DocumentoVigente,
    PasoPendiente,
    TipoDocumentoLegal,
    documentos_a_aceptar,
)
from app.acceso.dominio.modelos import Accion, EventoAuditoria
from app.acceso.dominio.puertos import FabricaUnidadDeTrabajo, LimitadorSolicitudes, Reloj


class ConsultarDocumentos:
    """Términos y política vigentes, con la fecha en que la cuenta los aceptó (si lo hizo)."""

    def __init__(self, unidad: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, sesion: SesionActiva) -> list[DocumentoVigente]:
        with self._unidad() as uow:
            vigentes = uow.documentos.vigentes(self._reloj())
            aceptados = uow.documentos.aceptaciones(sesion.usuario.id, [d.id for d in vigentes])
        return [DocumentoVigente(d, aceptados.get(d.id)) for d in vigentes]


class AceptarDocumentos:
    def __init__(self, unidad: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(
        self, sesion: SesionActiva, aceptados: Mapping[TipoDocumentoLegal, int]
    ) -> SesionActiva:
        """Registra la aceptación explícita de las versiones vigentes. Repetirla no la duplica."""
        with self._unidad() as uow:
            ahora = self._reloj()
            # La fila del usuario serializa dos envíos simultáneos de la misma cuenta.
            usuario = uow.usuarios.por_id(sesion.usuario.id, bloquear=True)
            if usuario is None or usuario.bloqueada or usuario.eliminada:
                raise NoAutenticado()
            documentos = documentos_a_aceptar(uow.documentos.vigentes(ahora), aceptados)
            registrar = uow.documentos.registrar_aceptacion
            nuevos = [d for d in documentos if registrar(usuario.id, d.id, ahora)]
            if nuevos:
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.DOCUMENTOS_ACEPTADOS,
                        actor_id=usuario.id,
                        cuenta_id=usuario.id,
                        detalle={
                            "documentos": [
                                {"tipo": d.tipo.value, "version": d.version} for d in nuevos
                            ]
                        },
                    )
                )
            pasos = pasos_de(uow, usuario, ahora)
        return SesionActiva(sesion.sesion_id, usuario, pasos)


class ConfirmarDatos:
    """Paso obligatorio de una asistente recién registrada (o recuperada): completa su correo y
    revisa lo que registró su gerente. Es la primera confirmación, así que aún puede corregir su
    documento si su gerente lo escribió mal; después solo cambia según las reglas de Mi cuenta."""

    def __init__(
        self,
        unidad: FabricaUnidadDeTrabajo,
        limitador: LimitadorSolicitudes,
        limites: LimitesAcceso,
        reloj: Reloj,
    ) -> None:
        self._unidad = unidad
        self._limitador = limitador
        self._limites = limites
        self._reloj = reloj

    def ejecutar(self, sesion: SesionActiva, nuevos: DatosPersonales) -> SesionActiva:
        exigir_cupo(self._limitador, (self._limites.actualizacion_cuenta, str(sesion.usuario.id)))
        with self._unidad() as uow:
            ahora = self._reloj()
            usuario = uow.usuarios.por_id(sesion.usuario.id, bloquear=True)
            if usuario is None or usuario.bloqueada or usuario.eliminada:
                raise NoAutenticado()
            if not usuario.debe_confirmar_datos:
                raise DatosYaConfirmados()
            pasos = pasos_de(uow, usuario, ahora)
            if pasos[0] is not PasoPendiente.COMPLETAR_DATOS:
                raise IncorporacionPendiente(pasos)
            actual = uow.usuarios.ficha(usuario.id)
            assert actual is not None
            # El nombre en recibos es solo del gerente.
            nuevos = replace(nuevos, nombre_recibos=None)
            corregidos = [
                campo
                for campo in (
                    "nombres",
                    "apellidos",
                    "telefono",
                    "tipo_documento",
                    "numero_documento",
                )
                if getattr(actual.datos, campo) != getattr(nuevos, campo)
            ]
            uow.usuarios.actualizar_datos(usuario.id, nuevos)
            usuario.nombres = nuevos.nombres
            usuario.confirmar_datos(ahora)
            uow.usuarios.guardar(usuario)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.DATOS_CONFIRMADOS,
                    actor_id=usuario.id,
                    cuenta_id=usuario.id,
                    # Solo los nombres de los campos: los valores son datos personales.
                    detalle={"corregidos": corregidos},
                )
            )
            pasos = pasos_de(uow, usuario, ahora)
        return SesionActiva(sesion.sesion_id, usuario, pasos)
