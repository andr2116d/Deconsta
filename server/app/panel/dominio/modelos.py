"""El panel de inicio de cada rol, calculado en el backend.

Gerente («Resumen»): cuánto falta pagar, lo pagado en el mes, la bandeja de lo que espera su
decisión (deudas por autorizar o por revisar, pagos por verificar y moras por aprobar), de la más
próxima a vencer a la más lejana, y los próximos pagos para pedir que los paguen.

Asistente («Mi jornada»): cuántos pagos puede completar, cuántos le devolvieron, lo suyo que espera
al gerente y su siguiente pago: primero el que le pidió el gerente; si no hay, el que vence antes.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.deudas.dominio.modelos import LugarPago


class TipoPendiente(StrEnum):
    AUTORIZAR_DEUDA = "autorizar_deuda"
    REVISAR_DEUDA = "revisar_deuda"
    VERIFICAR_PAGO = "verificar_pago"
    APROBAR_MORA = "aprobar_mora"


@dataclass(frozen=True)
class Pendiente:
    tipo: TipoPendiente
    # El id de la deuda, del pago o de la mora, según el tipo.
    id: UUID
    deuda_id: UUID
    concepto: str
    importe: Decimal
    vence_el: date
    # Quién lo dejó para el gerente.
    por: UUID
    desde: datetime


@dataclass(frozen=True)
class CuotaProxima:
    deuda_id: UUID
    concepto: str
    categoria_id: UUID | None
    cuota: int
    cuotas: int
    importe: Decimal
    vence_el: date
    lugares_pago: tuple[LugarPago, ...]
    # El pedido pendiente del gerente para pagarla, si lo hay.
    pedido_id: UUID | None = None
    pedido_a: UUID | None = None
    nota: str | None = None


@dataclass(frozen=True)
class PanelGerente:
    por_pagar: Decimal
    cuotas_por_pagar: int
    vencidas: int
    pagado_mes: Decimal
    pagos_mes: int
    pendientes: list[Pendiente]
    proximas: list[CuotaProxima]


@dataclass(frozen=True)
class PanelAsistente:
    por_completar: int
    # Cuotas por pagar cuyo último pago lo devolvió el gerente.
    devueltas: int
    # Lo que la asistente dejó y espera al gerente.
    en_manos_del_gerente: int
    siguiente: CuotaProxima | None
    # Sobre este importe, lo que registre espera la autorización; None: sin límite.
    limite: Decimal | None
