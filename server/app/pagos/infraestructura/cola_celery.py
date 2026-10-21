"""Cola del análisis de comprobantes de pago (Celery sobre Redis), en la misma cola ocr de los
documentos: el análisis usa el mismo motor de lectura.

La API solo publica el id del comprobante con send_task. Sin reintentos de conexión al publicar:
si Redis no responde, la subida falla rápido.
"""

from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError

from app.documentos.dominio.puertos import ErrorCola
from app.documentos.infraestructura.cola_celery import COLA_OCR

TAREA_ANALIZAR_COMPROBANTE = "pagos.analizar_comprobante"


class ColaComprobantesCelery:
    def __init__(self, aplicacion: Celery) -> None:
        self._aplicacion = aplicacion

    def encolar(self, comprobante_id: UUID) -> None:
        try:
            self._aplicacion.send_task(
                TAREA_ANALIZAR_COMPROBANTE, args=[str(comprobante_id)], queue=COLA_OCR, retry=False
            )
        except (OperationalError, OSError) as error:
            raise ErrorCola("La cola de análisis no respondió") from error
