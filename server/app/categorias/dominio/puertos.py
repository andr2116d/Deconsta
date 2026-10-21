"""Puertos de las categorías: lo que los casos de uso necesitan del exterior."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.puertos import RegistroAuditoria
from app.categorias.dominio.modelos import Categoria


class RepositorioCategorias(Protocol):
    def bloquear_espacio(self, gerente_id: UUID) -> bool:
        """Toma la fila del gerente con FOR UPDATE: las escrituras simultáneas en un mismo espacio
        se atienden una tras otra. False si el gerente ya no existe."""
        ...

    def del_espacio(self, gerente_id: UUID, *, incluir_archivadas: bool) -> list[Categoria]:
        """Las activas primero, cada grupo por nombre."""
        ...

    def por_id(self, gerente_id: UUID, categoria_id: UUID) -> Categoria | None:
        """Solo dentro del espacio indicado: la de otro espacio no existe para este."""
        ...

    def por_clave(self, gerente_id: UUID, clave: str) -> Categoria | None: ...

    def contar_activas(self, gerente_id: UUID) -> int: ...

    def contar(self, gerente_id: UUID) -> int:
        """Todas, incluidas las archivadas."""
        ...

    def agregar(self, categoria: Categoria) -> None:
        """Lanza CategoriaDuplicada si el nombre ya existe en el espacio."""
        ...

    def guardar(self, categoria: Categoria) -> None:
        """Lanza CategoriaDuplicada si el nombre nuevo ya existe en el espacio."""
        ...


class UnidadCategorias(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def categorias(self) -> RepositorioCategorias: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadCategorias = Callable[[], UnidadCategorias]
