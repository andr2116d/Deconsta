"""El historial del espacio: cada deuda con sus cuotas, sus pagos (también los devueltos), sus moras
y la línea de tiempo de quién hizo qué y cuándo, que sale de la auditoría.

Es de solo lectura. Lo ve todo el espacio; la confianza de los pagos, solo el gerente. Un rango de
fechas toma las deudas con actividad en esos días (registro, decisiones, pagos, moras o pedidos).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.deudas.dominio.modelos import EstadoDeuda, EstadoPago, LugarPago
from app.documentos.dominio.modelos import TipoDocumento
from app.pagos.dominio.modelos import EstadoMora

# Un año como máximo por consulta: más que eso se pide por partes.
RANGO_MAXIMO_DIAS = 366
DIAS_POR_DEFECTO = 90
LARGO_BUSQUEDA = 80


class EstadoFiltro(StrEnum):
    """El estado de la deuda, el de alguno de sus pagos o que tenga una mora."""

    POR_AUTORIZAR = "por_autorizar"
    REGISTRADA = "registrada"
    RECHAZADA = "rechazada"
    ANULADA = "anulada"
    POR_VERIFICAR = "por_verificar"
    CONFIRMADO = "confirmado"
    DEVUELTO = "devuelto"
    MORA = "mora"


ESTADOS_DEUDA = {
    EstadoFiltro.POR_AUTORIZAR,
    EstadoFiltro.REGISTRADA,
    EstadoFiltro.RECHAZADA,
    EstadoFiltro.ANULADA,
}
ESTADOS_PAGO = {EstadoFiltro.POR_VERIFICAR, EstadoFiltro.CONFIRMADO, EstadoFiltro.DEVUELTO}


@dataclass(frozen=True)
class Filtros:
    desde: date
    hasta: date
    estado: EstadoFiltro | None = None
    categoria_id: UUID | None = None
    registrada_por: UUID | None = None
    pagado_por: UUID | None = None
    # Dónde se puede pagar la deuda.
    lugar_pago: LugarPago | None = None
    # Busca en el concepto: el código de pago está cifrado y no se busca.
    texto: str | None = None
    # «Mis registros»: lo que la cuenta registró o pagó.
    de_la_cuenta: UUID | None = None


@dataclass(frozen=True)
class Posicion:
    """Dónde sigue la página siguiente: las deudas van de la más reciente a la más antigua."""

    creado_en: datetime
    id: UUID


@dataclass(frozen=True)
class CuotaHistorial:
    numero: int
    vence_el: date
    importe: Decimal


@dataclass(frozen=True)
class PagoHistorial:
    id: UUID
    cuota: int
    importe: Decimal
    comision: Decimal
    mora: Decimal
    lugar_pago: LugarPago | None
    pagado_el: date
    estado: EstadoPago
    confianza: int
    registrado_por: UUID
    registrado_en: datetime
    decidido_en: datetime | None
    motivo_decision: str | None


@dataclass(frozen=True)
class MoraHistorial:
    id: UUID
    cuota: int
    importe: Decimal
    estado: EstadoMora
    declarada_por: UUID
    declarada_en: datetime
    decidida_en: datetime | None
    motivo_decision: str | None


@dataclass(frozen=True)
class Evento:
    """Una acción de la auditoría sobre la deuda: DEUDA_*, PAGO_*, MORA_* o PEDIDO_*."""

    accion: str
    en: datetime
    actor_id: UUID | None
    motivo: str | None
    cuota: int | None


@dataclass(frozen=True)
class DeudaHistorial:
    id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    lugares_pago: tuple[LugarPago, ...]
    importe: Decimal
    estado: EstadoDeuda
    revision_pendiente: bool
    # Por qué esperó la autorización del gerente (IMPORTE_SOBRE_LIMITE…).
    motivos: tuple[str, ...]
    registrada_por: UUID
    creado_en: datetime
    motivo_decision: str | None
    cuotas: tuple[CuotaHistorial, ...]
    pagos: tuple[PagoHistorial, ...]
    moras: tuple[MoraHistorial, ...]
    eventos: tuple[Evento, ...]

    @property
    def posicion(self) -> Posicion:
        return Posicion(self.creado_en, self.id)

    def pago_vigente(self, cuota: int) -> PagoHistorial | None:
        return next(
            (p for p in self.pagos if p.cuota == cuota and p.estado is not EstadoPago.DEVUELTO),
            None,
        )

    def actores(self) -> set[UUID]:
        ids = {self.registrada_por}
        ids.update(p.registrado_por for p in self.pagos)
        ids.update(m.declarada_por for m in self.moras)
        ids.update(e.actor_id for e in self.eventos if e.actor_id)
        return ids
