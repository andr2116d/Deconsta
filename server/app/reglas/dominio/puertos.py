"""Puertos de las reglas de autorización: lo que los casos de uso necesitan del exterior."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.puertos import RegistroAuditoria
from app.reglas.dominio.titulares import TitularAutorizado


@dataclass(frozen=True)
class ReglaAutorizacion:
    limite_importe: Decimal | None
    actualizado_en: datetime


class RepositorioReglas(Protocol):
    def bloquear_espacio(self, gerente_id: UUID) -> bool:
        """Toma la fila del gerente con FOR UPDATE: las escrituras simultáneas en un mismo espacio
        se atienden una tras otra. False si el gerente ya no existe."""
        ...

    def regla(self, gerente_id: UUID) -> ReglaAutorizacion | None: ...

    def guardar_limite(
        self, gerente_id: UUID, limite: Decimal | None, actualizado_por: UUID
    ) -> ReglaAutorizacion: ...

    def titulares(self, gerente_id: UUID) -> list[TitularAutorizado]:
        """Los vigentes, con sus datos descifrados, por nombre."""
        ...

    def titular(self, gerente_id: UUID, titular_id: UUID) -> TitularAutorizado | None:
        """Solo un vigente del espacio indicado."""
        ...

    def agregar_titular(self, titular: TitularAutorizado) -> None:
        """Lanza TitularDuplicado si el nombre o el documento ya están entre los vigentes."""
        ...

    def guardar_titular(self, titular: TitularAutorizado) -> None:
        """Lanza TitularDuplicado si el nombre nuevo ya está entre los vigentes."""
        ...

    def ficha_gerente(self, gerente_id: UUID) -> FichaPersonal | None:
        """Datos del gerente, descifrados: él siempre es un titular reconocido."""
        ...


class UnidadReglas(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def reglas(self) -> RepositorioReglas: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadReglas = Callable[[], UnidadReglas]
