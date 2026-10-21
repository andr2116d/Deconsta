"""Deudas del espacio de un gerente.

Estados y transiciones:

- por_autorizar: la registró una asistente y supera el límite, tiene otro titular, su documento es
  dudoso o se corrigió el importe o el código de pago respecto de lo que dice el documento. No se
  paga hasta que el gerente la autorice (→ registrada) o la rechace con un motivo (→ rechazada).
- registrada: se puede pagar. Si la registró una asistente sin excepciones, queda con la revisión
  pendiente: el gerente le da su visto bueno (sale de sus pendientes) o la anula con un motivo
  (→ anulada). Mientras no la anule, sigue registrada y se puede pagar.
- rechazada y anulada son finales.

Lo que registra el gerente queda registrada, sin revisión pendiente.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.deudas.dominio.errores import TransicionInvalida
from app.documentos.dominio.modelos import TipoDocumento
from app.reglas.dominio.titulares import Documento


class LugarPago(StrEnum):
    VENTANILLA = "ventanilla"
    AGENTE = "agente"
    BANCA_DIGITAL = "banca_digital"
    TRANSFERENCIA = "transferencia"
    BILLETERA = "billetera"
    DEBITO_AUTOMATICO = "debito_automatico"


class EstadoDeuda(StrEnum):
    POR_AUTORIZAR = "por_autorizar"
    REGISTRADA = "registrada"
    RECHAZADA = "rechazada"
    ANULADA = "anulada"


class MotivoEspera(StrEnum):
    IMPORTE_SOBRE_LIMITE = "IMPORTE_SOBRE_LIMITE"
    TITULAR_DISTINTO = "TITULAR_DISTINTO"
    DOCUMENTO_DUDOSO = "DOCUMENTO_DUDOSO"
    DATOS_CORREGIDOS = "DATOS_CORREGIDOS"


@dataclass(frozen=True)
class Cuota:
    numero: int
    vence_el: date
    importe: Decimal


@dataclass
class Deuda:
    id: UUID
    gerente_id: UUID
    registrada_por: UUID
    documento_id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    cuotas: tuple[Cuota, ...]
    # Dónde se puede pagar: uno o varios, sin repetir y en el orden de LugarPago.
    lugares_pago: tuple[LugarPago, ...]
    titular_nombre: str | None
    titular_documento: Documento | None
    codigo_pago: str | None
    estado: EstadoDeuda
    creado_en: datetime
    motivos: tuple[MotivoEspera, ...] = ()
    revision_pendiente: bool = False
    campos_corregidos: tuple[str, ...] = ()
    decidida_por: UUID | None = None
    decidida_en: datetime | None = None
    motivo_decision: str | None = None

    @property
    def importe(self) -> Decimal:
        return sum((c.importe for c in self.cuotas), Decimal("0"))

    @property
    def vence_el(self) -> date:
        return min(c.vence_el for c in self.cuotas)

    def vencida_hace(self, hoy: date) -> int | None:
        """Días desde que venció su primera cuota; None si aún no vence o ya no se paga. Una
        deuda vencida se registra y se paga igual: la empresa puede cobrar mora."""
        if self.estado not in (EstadoDeuda.POR_AUTORIZAR, EstadoDeuda.REGISTRADA):
            return None
        dias = (hoy - self.vence_el).days
        return dias if dias > 0 else None

    @property
    def pendiente_para_gerente(self) -> bool:
        return self.estado is EstadoDeuda.POR_AUTORIZAR or self.revision_pendiente

    def _decidir(self, por: UUID, ahora: datetime, motivo: str | None = None) -> None:
        self.decidida_por = por
        self.decidida_en = ahora
        self.motivo_decision = motivo

    def autorizar(self, por: UUID, ahora: datetime) -> None:
        if self.estado is not EstadoDeuda.POR_AUTORIZAR:
            raise TransicionInvalida(self._ya_decidida())
        self.estado = EstadoDeuda.REGISTRADA
        self.revision_pendiente = False
        self._decidir(por, ahora)

    def rechazar(self, por: UUID, ahora: datetime, motivo: str) -> None:
        if self.estado is not EstadoDeuda.POR_AUTORIZAR:
            raise TransicionInvalida(
                self._ya_decidida()
                if self.estado is not EstadoDeuda.REGISTRADA
                else "Esta deuda no espera tu autorización. Si no corresponde, anúlala."
            )
        self.estado = EstadoDeuda.RECHAZADA
        self._decidir(por, ahora, motivo)

    def dar_visto_bueno(self, por: UUID, ahora: datetime) -> None:
        if self.estado is EstadoDeuda.POR_AUTORIZAR:
            raise TransicionInvalida("Esta deuda espera tu autorización: autorízala o recházala.")
        if not self.revision_pendiente:
            raise TransicionInvalida(self._ya_decidida())
        self.revision_pendiente = False
        self._decidir(por, ahora)

    def anular(self, por: UUID, ahora: datetime, motivo: str) -> None:
        if self.estado is EstadoDeuda.POR_AUTORIZAR:
            raise TransicionInvalida(
                "Esta deuda espera tu autorización: si no corresponde, recházala."
            )
        if self.estado is not EstadoDeuda.REGISTRADA:
            raise TransicionInvalida(self._ya_decidida())
        self.estado = EstadoDeuda.ANULADA
        self.revision_pendiente = False
        self._decidir(por, ahora, motivo)

    def _ya_decidida(self) -> str:
        return {
            EstadoDeuda.RECHAZADA: "Esta deuda ya fue rechazada.",
            EstadoDeuda.ANULADA: "Esta deuda ya fue anulada.",
        }.get(self.estado, "Esta deuda ya fue revisada.")
