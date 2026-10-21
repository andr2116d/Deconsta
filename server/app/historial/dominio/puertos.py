from collections.abc import Callable, Iterable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.documentos.dominio.puertos import RepositorioCuentas
from app.historial.dominio.modelos import DeudaHistorial, Filtros, Posicion


class RepositorioHistorial(Protocol):
    def buscar(
        self,
        gerente_id: UUID,
        filtros: Filtros,
        inicio: datetime,
        fin: datetime,
        despues: Posicion | None,
        limite: int,
    ) -> list[DeudaHistorial]:
        """Las deudas del espacio con actividad entre `inicio` (incluido) y `fin` (excluido), de la
        más reciente a la más antigua, después de `despues`."""
        ...

    def usuarios(self, ids: Iterable[UUID]) -> dict[UUID, str]:
        """El nombre de usuario de cada cuenta: no es un dato cifrado."""
        ...

    def categorias(self, gerente_id: UUID) -> dict[UUID, str]: ...


class UnidadHistorial(Protocol):
    """Solo lectura: al salir se cierra la transacción."""

    @property
    def historial(self) -> RepositorioHistorial: ...

    @property
    def cuentas(self) -> RepositorioCuentas: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadHistorial = Callable[[], UnidadHistorial]
