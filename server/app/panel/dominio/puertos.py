from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.documentos.dominio.puertos import RepositorioCuentas
from app.panel.dominio.modelos import CuotaProxima, Pendiente


class RepositorioPanel(Protocol):
    def por_pagar(self, gerente_id: UUID, hoy: date) -> tuple[Decimal, int, int]:
        """Importe, cuotas y cuántas ya vencieron, de las deudas registradas sin pago vigente."""
        ...

    def pagado_entre(self, gerente_id: UUID, desde: date, hasta: date) -> tuple[Decimal, int]:
        """Lo pagado (por verificar o confirmado) con fecha de pago en el rango, y cuántos pagos."""
        ...

    def pendientes(self, gerente_id: UUID) -> list[Pendiente]: ...

    def proximas(self, gerente_id: UUID, limite: int) -> list[CuotaProxima]:
        """Las cuotas por pagar que vencen antes, con su pedido pendiente si lo hay."""
        ...

    def pedidas_a(self, asistente_id: UUID) -> list[CuotaProxima]:
        """Las cuotas que el gerente pidió pagar a la asistente y siguen por pagar."""
        ...

    def devueltas(self, gerente_id: UUID) -> int: ...

    def en_espera_de(self, asistente_id: UUID) -> int:
        """Sus deudas por autorizar, sus pagos por verificar y sus moras por aprobar."""
        ...

    def limite(self, gerente_id: UUID) -> Decimal | None: ...


class UnidadPanel(Protocol):
    """Solo lectura: al salir se cierra la transacción."""

    @property
    def panel(self) -> RepositorioPanel: ...

    @property
    def cuentas(self) -> RepositorioCuentas: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...
