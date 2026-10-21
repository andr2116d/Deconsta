"""Notificaciones de cada cuenta.

Cada una corresponde a un evento real (una deuda registrada, una decisión del gerente, un bloqueo)
y se guarda en la misma transacción que ese evento: si el evento no ocurre, no hay notificación, y
la clave del evento impide repetirla. El aviso en tiempo real solo anuncia que hay una nueva.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class TipoNotificacion(StrEnum):
    # Para el gerente.
    DEUDA_POR_AUTORIZAR = "DEUDA_POR_AUTORIZAR"
    DEUDA_REGISTRADA = "DEUDA_REGISTRADA"
    REGISTRO_BLOQUEADO = "REGISTRO_BLOQUEADO"
    PAGO_POR_VERIFICAR = "PAGO_POR_VERIFICAR"
    REGISTRO_PAGOS_BLOQUEADO = "REGISTRO_PAGOS_BLOQUEADO"
    MORA_POR_APROBAR = "MORA_POR_APROBAR"
    # Para la asistente.
    DEUDA_AUTORIZADA = "DEUDA_AUTORIZADA"
    DEUDA_RECHAZADA = "DEUDA_RECHAZADA"
    DEUDA_ANULADA = "DEUDA_ANULADA"
    REGISTRO_DESBLOQUEADO = "REGISTRO_DESBLOQUEADO"
    REGISTRO_PAGOS_DESBLOQUEADO = "REGISTRO_PAGOS_DESBLOQUEADO"
    PAGO_CONFIRMADO = "PAGO_CONFIRMADO"
    PAGO_DEVUELTO = "PAGO_DEVUELTO"
    MORA_APROBADA = "MORA_APROBADA"
    MORA_RECHAZADA = "MORA_RECHAZADA"
    PAGO_PEDIDO = "PAGO_PEDIDO"
    PEDIDO_RETIRADO = "PEDIDO_RETIRADO"


@dataclass(frozen=True)
class Notificacion:
    id: UUID
    destinatario_id: UUID
    tipo: TipoNotificacion
    clave_evento: str
    titulo: str
    cuerpo: str
    creada_en: datetime
    deuda_id: UUID | None = None
    cuenta_id: UUID | None = None
    leida_en: datetime | None = None

    @property
    def leida(self) -> bool:
        return self.leida_en is not None


def nueva_notificacion(
    destinatario_id: UUID,
    tipo: TipoNotificacion,
    clave_evento: str,
    titulo: str,
    cuerpo: str,
    ahora: datetime,
    *,
    deuda_id: UUID | None = None,
    cuenta_id: UUID | None = None,
) -> Notificacion:
    return Notificacion(
        uuid4(), destinatario_id, tipo, clave_evento, titulo, cuerpo, ahora, deuda_id, cuenta_id
    )
