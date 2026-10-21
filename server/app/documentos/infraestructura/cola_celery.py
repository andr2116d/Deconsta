"""Cola del análisis de documentos (Celery sobre Redis).

La API solo publica el id del documento con send_task: no importa el código del worker ni
PaddleOCR. Sin reintentos de conexión al publicar: si Redis no responde, la subida falla rápido y
el documento no queda esperando un análisis que nunca llegará.
"""

from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError

from app.documentos.dominio.puertos import ErrorCola

TAREA_ANALIZAR = "documentos.analizar"
COLA_OCR = "ocr"


class ColaCelery:
    def __init__(self, aplicacion: Celery) -> None:
        self._aplicacion = aplicacion

    def encolar(self, documento_id: UUID) -> None:
        try:
            self._aplicacion.send_task(
                TAREA_ANALIZAR, args=[str(documento_id)], queue=COLA_OCR, retry=False
            )
        except (OperationalError, OSError) as error:
            raise ErrorCola("La cola de análisis no respondió") from error
