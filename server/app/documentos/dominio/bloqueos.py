"""Bloqueo del registro de deudas por documentos repetidos.

Cada vez que una asistente sube un documento que ya respalda otra deuda del espacio, queda un
intento. Al tercero en 24 horas se bloquea su registro de deudas (no su cuenta: puede seguir con
sus demás tareas) y se avisa a su gerente, que es quien lo levanta. Los intentos anteriores a un
levantamiento ya no cuentan. Al gerente nunca se le bloquea: solo se le advierte.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

MAXIMO_REPETIDOS = 3
VENTANA_REPETIDOS = timedelta(hours=24)


@dataclass(frozen=True)
class Bloqueo:
    id: UUID
    asistente_id: UUID
    gerente_id: UUID
    bloqueado_en: datetime


def contar_desde(ahora: datetime, ultimo_levantamiento: datetime | None) -> datetime:
    """Desde cuándo cuentan los intentos: las últimas 24 horas o el último levantamiento."""
    inicio = ahora - VENTANA_REPETIDOS
    return max(inicio, ultimo_levantamiento) if ultimo_levantamiento else inicio
