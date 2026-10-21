from collections.abc import Mapping

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.dominio.errores import IncorporacionPendiente, NoAutenticado
from app.acceso.dominio.incorporacion import (
    DocumentoVigente,
    PasoPendiente,
    TipoDocumentoLegal,
    documentos_a_aceptar,
    pasos_pendientes,
)
from app.acceso.dominio.modelos import Accion, EventoAuditoria
from app.acceso.dominio.puertos import FabricaUnidadDeTrabajo, Reloj


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
            if usuario is None or usuario.bloqueada:
                raise NoAutenticado()
            if usuario.debe_cambiar_contrasena:
                raise IncorporacionPendiente([PasoPendiente.CAMBIAR_CONTRASENA])
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
            pasos = pasos_pendientes(usuario, uow.documentos.hay_sin_aceptar(usuario.id, ahora))
        return SesionActiva(sesion.sesion_id, usuario, pasos)
