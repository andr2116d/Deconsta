from uuid import UUID

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.dominio.errores import CuentaNoBloqueada, CuentaNoEncontrada, SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol, Usuario
from app.acceso.dominio.puertos import FabricaUnidadDeTrabajo, LimitadorSolicitudes


class DesbloquearAsistente:
    def __init__(
        self,
        unidad: FabricaUnidadDeTrabajo,
        limitador: LimitadorSolicitudes,
        limites: LimitesAcceso,
    ) -> None:
        self._unidad = unidad
        self._limitador = limitador
        self._limites = limites

    def ejecutar(self, sesion: SesionActiva, asistente_id: UUID, motivo: str | None) -> Usuario:
        gerente = sesion.usuario
        if gerente.rol is not Rol.GERENTE:
            raise SinPermiso()
        exigir_cupo(self._limitador, (self._limites.desbloqueo, str(gerente.id)))
        with self._unidad() as uow:
            asistente = uow.usuarios.por_id(asistente_id, bloquear=True)
            # Una asistente de otro equipo responde igual que una inexistente: no se revela.
            if (
                asistente is None
                or asistente.rol is not Rol.ASISTENTE
                or asistente.gerente_id != gerente.id
            ):
                raise CuentaNoEncontrada()
            if not asistente.bloqueada:
                raise CuentaNoBloqueada()
            intentos = asistente.intentos_fallidos
            asistente.desbloquear()
            uow.usuarios.guardar(asistente)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_DESBLOQUEADA,
                    actor_id=gerente.id,
                    cuenta_id=asistente.id,
                    motivo=motivo,
                    detalle={"intentos_fallidos": intentos},
                )
            )
        return asistente
