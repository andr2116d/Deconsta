"""Cola del análisis de comprobantes de pago (Celery sobre Redis). Tiene su propia cola, pagos, para
que un voucher no espere detrás de los documentos de deudas: en producción la atiende un worker
dedicado.

La API solo publica el id del comprobante con send_task. Sin reintentos de conexión al publicar:
si Redis no responde, la subida falla rápido.
"""

from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError

from app.documentos.dominio.puertos import ErrorCola

TAREA_ANALIZAR_COMPROBANTE = "pagos.analizar_comprobante"
COLA_PAGOS = "pagos"


class ColaComprobantesCelery:
    def __init__(self, aplicacion: Celery) -> None:
        self._aplicacion = aplicacion

    def encolar(self, comprobante_id: UUID) -> None:
        try:
            self._aplicacion.send_task(
                TAREA_ANALIZAR_COMPROBANTE,
                args=[str(comprobante_id)],
                queue=COLA_PAGOS,
                retry=False,
            )
        except (OperationalError, OSError) as error:
            raise ErrorCola("La cola de análisis no respondió") from error
