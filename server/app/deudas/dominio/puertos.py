"""Puertos de las deudas: lo que los casos de uso necesitan del exterior."""

from collections.abc import Callable
from datetime import date
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.puertos import RegistroAuditoria
from app.categorias.dominio.puertos import RepositorioCategorias
from app.deudas.dominio.modelos import Deuda
from app.documentos.dominio.puertos import (
    RepositorioBloqueos,
    RepositorioCuentas,
    RepositorioDocumentos,
)
from app.notificaciones.dominio.puertos import RepositorioNotificaciones
from app.reglas.dominio.puertos import RepositorioReglas


class RepositorioDeudas(Protocol):
    def agregar(self, deuda: Deuda) -> None:
        """Guarda la deuda con sus cuotas y la vincula a su documento. Lanza
        DocumentoNoRegistrable("DOCUMENTO_YA_USADO") si ese documento, o uno con el mismo archivo
        o la misma clave de negocio, ya respalda otra deuda del espacio."""
        ...

    def por_id(self, deuda_id: UUID, *, bloquear: bool = False) -> Deuda | None: ...

    def guardar(self, deuda: Deuda) -> None:
        """Guarda el estado, la revisión y la decisión. Las cuotas y los datos no cambian."""
        ...

    def del_espacio(self, gerente_id: UUID, *, solo_pendientes: bool) -> list[Deuda]:
        """Las más recientes primero."""
        ...

    def con_vencimientos_entre(self, gerente_id: UUID, desde: date, hasta: date) -> list[Deuda]:
        """Las deudas vigentes (por autorizar o registradas) con alguna cuota que vence en el
        rango, ambos días incluidos."""
        ...


class UnidadDeudas(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def deudas(self) -> RepositorioDeudas: ...

    @property
    def documentos(self) -> RepositorioDocumentos: ...

    @property
    def categorias(self) -> RepositorioCategorias: ...

    @property
    def reglas(self) -> RepositorioReglas: ...

    @property
    def bloqueos(self) -> RepositorioBloqueos: ...

    @property
    def cuentas(self) -> RepositorioCuentas: ...

    @property
    def notificaciones(self) -> RepositorioNotificaciones: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadDeudas = Callable[[], UnidadDeudas]
