"""Casos de uso de las notificaciones. Cada cuenta ve y marca solo las suyas."""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.dominio.puertos import Reloj
from app.notificaciones.dominio.errores import NotificacionNoEncontrada
from app.notificaciones.dominio.modelos import Notificacion
from app.notificaciones.dominio.puertos import (
    FabricaUnidadNotificaciones,
    PublicadorAvisos,
    RepositorioNotificaciones,
)

logger = logging.getLogger(__name__)

MAXIMO_LISTADO = 50


class Avisos:
    """Junta las notificaciones que se guardan en una transacción y las anuncia en tiempo real
    solo después de confirmarla: así nunca se avisa de algo que se revirtió."""

    def __init__(self, publicador: PublicadorAvisos) -> None:
        self._publicador = publicador
        self._pendientes: list[Notificacion] = []

    def guardar(self, repositorio: RepositorioNotificaciones, notificacion: Notificacion) -> None:
        if repositorio.agregar(notificacion):
            self._pendientes.append(notificacion)

    def enviar(self) -> None:
        for notificacion in self._pendientes:
            try:
                self._publicador.avisar(notificacion)
            except Exception:
                # Ya está guardada: la verá al abrir sus notificaciones o al recargar.
                logger.warning(
                    "No se pudo avisar en tiempo real la notificación %s", notificacion.id
                )
        self._pendientes.clear()


@dataclass(frozen=True)
class Bandeja:
    notificaciones: list[Notificacion]
    no_leidas: int


class _OperacionNotificaciones:
    def __init__(self, unidad: FabricaUnidadNotificaciones, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj


class ListarNotificaciones(_OperacionNotificaciones):
    def ejecutar(self, sesion: SesionActiva) -> Bandeja:
        with self._unidad() as uow:
            repositorio = uow.notificaciones
            usuario_id = sesion.usuario.id
            return Bandeja(
                repositorio.de(usuario_id, MAXIMO_LISTADO),
                repositorio.contar_no_leidas(usuario_id),
            )


class MarcarLeida(_OperacionNotificaciones):
    def ejecutar(self, sesion: SesionActiva, notificacion_id: UUID) -> None:
        with self._unidad() as uow:
            if not uow.notificaciones.marcar_leida(
                sesion.usuario.id, notificacion_id, self._reloj()
            ):
                raise NotificacionNoEncontrada()


class MarcarTodasLeidas(_OperacionNotificaciones):
    def ejecutar(self, sesion: SesionActiva) -> int:
        with self._unidad() as uow:
            return uow.notificaciones.marcar_todas_leidas(sesion.usuario.id, self._reloj())
