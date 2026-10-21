from dataclasses import dataclass
from uuid import UUID

from app.acceso.dominio.errores import NoAutenticado
from app.acceso.dominio.incorporacion import PasoPendiente, pasos_pendientes
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Usuario, huella_token
from app.acceso.dominio.puertos import FabricaUnidadDeTrabajo, Reloj


@dataclass(frozen=True)
class SesionActiva:
    sesion_id: UUID
    usuario: Usuario
    # Se recalculan en cada solicitud: si se publica una versión nueva de los documentos, las
    # sesiones abiertas vuelven a pedir la aceptación.
    pasos_pendientes: tuple[PasoPendiente, ...] = ()


class Autenticar:
    def __init__(self, unidad: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, token: str | None) -> SesionActiva:
        if not token:
            raise NoAutenticado()
        with self._unidad() as uow:
            ahora = self._reloj()
            sesion = uow.sesiones.vigente(huella_token(token), ahora)
            usuario = uow.usuarios.por_id(sesion.usuario_id, bloquear=False) if sesion else None
            if sesion is None or usuario is None or usuario.bloqueada:
                raise NoAutenticado()
            pasos = pasos_pendientes(uow.documentos.hay_sin_aceptar(usuario.id, ahora))
        return SesionActiva(sesion.id, usuario, pasos)


class CerrarSesion:
    def __init__(self, unidad: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, token: str | None) -> None:
        """Revoca la sesión si sigue vigente. Cerrar una sesión ya cerrada no es un error."""
        if not token:
            return
        with self._unidad() as uow:
            ahora = self._reloj()
            sesion = uow.sesiones.vigente(huella_token(token), ahora)
            if sesion is None:
                return
            uow.sesiones.revocar(sesion.id, ahora, "cierre_sesion")
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CIERRE_SESION, actor_id=sesion.usuario_id, cuenta_id=sesion.usuario_id
                )
            )
