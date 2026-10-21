"""Puertos de las notificaciones."""

from collections.abc import AsyncIterator, Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.notificaciones.dominio.modelos import Notificacion


class RepositorioNotificaciones(Protocol):
    def agregar(self, notificacion: Notificacion) -> bool:
        """Guarda la notificación. False si ya existía una con la misma clave de evento para ese
        destinatario: el evento ya se notificó."""
        ...

    def de(self, destinatario_id: UUID, limite: int) -> list[Notificacion]:
        """Las más recientes primero."""
        ...

    def contar_no_leidas(self, destinatario_id: UUID) -> int: ...

    def marcar_leida(self, destinatario_id: UUID, notificacion_id: UUID, ahora: datetime) -> bool:
        """Solo una del propio destinatario. False si no existe para él."""
        ...

    def marcar_todas_leidas(self, destinatario_id: UUID, ahora: datetime) -> int: ...


class PublicadorAvisos(Protocol):
    """Avisa en tiempo real a las sesiones abiertas de una cuenta que tiene una notificación
    nueva. Un fallo no pierde nada: la notificación ya está guardada."""

    def avisar(self, notificacion: Notificacion) -> None: ...


class SuscriptorAvisos(Protocol):
    def escuchar(self, destinatario_id: UUID) -> AsyncIterator[str]:
        """Ids de las notificaciones nuevas del destinatario, a medida que llegan. Sin novedades,
        entrega "" cada segundo: así quien escucha puede enviar latidos o dejar de escuchar."""
        ...


class UnidadNotificaciones(Protocol):
    @property
    def notificaciones(self) -> RepositorioNotificaciones: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadNotificaciones = Callable[[], UnidadNotificaciones]
