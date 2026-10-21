"""Puertos de los pagos: lo que los casos de uso necesitan del exterior."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.puertos import RegistroAuditoria
from app.deudas.dominio.modelos import EstadoPago
from app.deudas.dominio.puertos import RepositorioDeudas
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import Lectura, TipoArchivo
from app.documentos.dominio.puertos import RepositorioCuentas, RepositorioDocumentos
from app.notificaciones.dominio.puertos import RepositorioNotificaciones
from app.pagos.dominio.modelos import Comprobante, DatosComprobante, EstadoMora, Mora, Pago


@dataclass(frozen=True)
class RevisionComprobante:
    legible: bool
    datos: DatosComprobante
    # autentico, dudoso o alterado.
    veredicto: str
    motivos: tuple[str, ...] = field(default=())


class RevisorComprobantes(Protocol):
    def revisar_comprobante(
        self, contenido: bytes, tipo: TipoArchivo, lectura: Lectura
    ) -> RevisionComprobante:
        """Lee el comprobante sin saber qué cuota dice pagar. Lanza ErrorRevision si el modelo no
        respondió o no dio una respuesta usable."""
        ...

    def revisar_prueba_mora(
        self, contenido: bytes, tipo: TipoArchivo, lectura: Lectura
    ) -> RevisionComprobante:
        """Lee la prueba de una mora (un documento de cobro o un voucher) sin saber qué mora se
        declarará. Lanza ErrorRevision como revisar_comprobante."""
        ...


class ColaComprobantes(Protocol):
    def encolar(self, comprobante_id: UUID) -> None:
        """Lanza ErrorCola si no se pudo encolar."""
        ...


class RepositorioComprobantes(Protocol):
    def agregar(self, comprobante: Comprobante) -> None: ...

    def por_id(self, comprobante_id: UUID, *, bloquear: bool = False) -> Comprobante | None: ...

    def guardar(self, comprobante: Comprobante) -> None:
        """Guarda el estado, el análisis y la huella de la operación."""
        ...

    def archivo_usado(self, gerente_id: UUID, huella: bytes) -> bool:
        """Si un archivo con esa huella ya respalda un pago del espacio."""
        ...

    def operacion_usada(self, gerente_id: UUID, huella: bytes) -> bool: ...

    def prueba_usada(self, gerente_id: UUID, huella: bytes) -> bool:
        """Si un archivo con esa huella ya prueba una mora del espacio."""
        ...

    def del_pago(self, pago_id: UUID) -> list[Comprobante]: ...

    def vincular(self, comprobantes: list[UUID], pago_id: UUID) -> None:
        """Lanza ComprobanteNoUsable("COMPROBANTE_YA_USADO") si el archivo o la operación de
        alguno ya respaldan otro pago del espacio."""
        ...


class RepositorioPagos(Protocol):
    def agregar(self, pago: Pago) -> None:
        """Lanza CuotaNoPagable("CUOTA_YA_PAGADA") si la cuota ya tiene un pago vigente."""
        ...

    def por_id(self, pago_id: UUID, *, bloquear: bool = False) -> Pago | None: ...

    def guardar(self, pago: Pago) -> None:
        """Guarda el estado y la decisión del gerente."""
        ...

    def del_espacio(self, gerente_id: UUID, *, estado: EstadoPago | None = None) -> list[Pago]:
        """Los más recientes primero, con los ids de sus comprobantes."""
        ...

    def devoluciones(self, gerente_id: UUID) -> dict[tuple[UUID, int], str]:
        """El motivo de la última devolución de cada cuota que sigue por pagar."""
        ...


class RepositorioMoras(Protocol):
    def agregar(self, mora: Mora) -> None:
        """Lanza CuotaNoPagable("MORA_YA_DECLARADA") si la cuota ya tiene una mora vigente y
        ComprobanteNoUsable("PRUEBA_YA_USADA") si la prueba ya respalda otra."""
        ...

    def por_id(self, mora_id: UUID, *, bloquear: bool = False) -> Mora | None: ...

    def guardar(self, mora: Mora) -> None:
        """Guarda el estado y la decisión del gerente."""
        ...

    def del_espacio(self, gerente_id: UUID, *, estado: EstadoMora | None = None) -> list[Mora]:
        """Las más recientes primero."""
        ...

    def de_la_cuota(self, deuda_id: UUID, cuota: int) -> Mora | None:
        """La vigente (por aprobar o aprobada) o, si no hay, la última rechazada."""
        ...

    def del_espacio_por_cuota(self, gerente_id: UUID) -> dict[tuple[UUID, int], Mora]:
        """La de cada cuota, como en de_la_cuota."""
        ...


class RepositorioBloqueosPagos(Protocol):
    def vigente(self, asistente_id: UUID) -> Bloqueo | None: ...

    def vigentes_del_espacio(self, gerente_id: UUID) -> list[Bloqueo]: ...

    def registrar_intento(
        self, asistente_id: UUID, comprobante_id: UUID, ahora: datetime
    ) -> None: ...

    def contar_intentos(self, asistente_id: UUID, desde: datetime) -> int: ...

    def ultimo_levantamiento(self, asistente_id: UUID) -> datetime | None: ...

    def bloquear(self, bloqueo: Bloqueo) -> bool:
        """False si ya tenía un bloqueo vigente."""
        ...

    def levantar(self, bloqueo_id: UUID, levantado_por: UUID, ahora: datetime) -> None: ...


class UnidadPagos(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def comprobantes(self) -> RepositorioComprobantes: ...

    @property
    def pagos(self) -> RepositorioPagos: ...

    @property
    def moras(self) -> RepositorioMoras: ...

    @property
    def deudas(self) -> RepositorioDeudas: ...

    @property
    def documentos(self) -> RepositorioDocumentos: ...

    @property
    def bloqueos(self) -> RepositorioBloqueosPagos: ...

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


FabricaUnidadPagos = Callable[[], UnidadPagos]
