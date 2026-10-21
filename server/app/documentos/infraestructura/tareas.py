"""Tarea del worker de la cola ocr: analiza un documento recién subido.

Reintenta con espera creciente lo que puede ser pasajero (el almacenamiento, la base o el motor de
lectura). Si agota los reintentos, o si el archivo resulta inválido, el documento queda «fallido»
para que la persona lo vuelva a subir; nunca queda «analizando» para siempre.
"""

import logging
import os
from functools import cache
from uuid import UUID

from celery import Task
from celery.signals import worker_process_init
from sqlalchemy.exc import OperationalError

from app.contenedor import ahora_utc
from app.core.config import settings
from app.core.database import crear_motor
from app.documentos.aplicacion.documentos import AnalizarDocumento, MarcarAnalisisFallido
from app.documentos.dominio.errores import ArchivoInvalido
from app.documentos.dominio.puertos import ErrorAlmacen, ErrorLectura
from app.documentos.infraestructura.cola_celery import TAREA_ANALIZAR
from app.documentos.infraestructura.componentes import Componentes
from app.documentos.infraestructura.lector_paddle import LectorPaddle
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REINTENTABLES = (ErrorAlmacen, ErrorLectura, OperationalError)


@cache
def componentes() -> Componentes:
    return Componentes.crear(settings, crear_motor(settings.database_url))


@worker_process_init.connect
def precargar(**_: object) -> None:
    """Carga el modelo de lectura al iniciar el proceso: la primera lectura no paga esa espera."""
    if os.environ.get("OCR_PRECARGAR", "").lower() == "true":
        try:
            lector = componentes().lector
            if isinstance(lector, LectorPaddle):
                lector.precargar()
        except Exception:
            logger.exception("No se pudo precargar el modelo de lectura")


def _analizar() -> AnalizarDocumento:
    c = componentes()
    return AnalizarDocumento(
        c.unidad,
        ahora_utc,
        c.publicador,
        almacen=c.almacen,
        inspector=c.inspector,
        lector=c.lector,
        revisor=c.revisor,
        huellero=c.cifrador,
    )


@celery_app.task(
    name=TAREA_ANALIZAR,
    bind=True,
    acks_late=True,
    max_retries=3,
    soft_time_limit=240,
    time_limit=300,
)
def analizar_documento(tarea: Task, documento_id: str) -> str | None:
    identificador = UUID(documento_id)
    try:
        estado = _analizar().ejecutar(identificador)
    except REINTENTABLES as error:
        if tarea.request.retries >= (tarea.max_retries or 0):
            logger.error("El análisis del documento %s agotó sus reintentos", documento_id)
            MarcarAnalisisFallido(
                componentes().unidad, ahora_utc, componentes().publicador
            ).ejecutar(identificador)
            return None
        raise tarea.retry(exc=error, countdown=5 * 2**tarea.request.retries) from error
    except ArchivoInvalido:
        logger.warning("El documento %s no se pudo procesar como archivo válido", documento_id)
        MarcarAnalisisFallido(componentes().unidad, ahora_utc, componentes().publicador).ejecutar(
            identificador
        )
        return None
    except Exception:
        # Un fallo del motor de lectura o de la IA que no se espera: se registra y el documento
        # queda «fallido» para que se vuelva a subir, en vez de esperar para siempre.
        logger.exception("El análisis del documento %s falló de forma inesperada", documento_id)
        MarcarAnalisisFallido(componentes().unidad, ahora_utc, componentes().publicador).ejecutar(
            identificador
        )
        return None
    return estado.value if estado else None
