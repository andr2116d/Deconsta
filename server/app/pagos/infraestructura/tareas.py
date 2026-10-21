"""Tarea del worker de la cola ocr: analiza un comprobante de pago recién subido.

Como la de los documentos: reintenta con espera creciente lo que puede ser pasajero y, si agota
los reintentos o el archivo resulta inválido, el comprobante queda «fallido» para que se vuelva a
subir; nunca queda «analizando» para siempre.
"""

import logging
from uuid import UUID
from zoneinfo import ZoneInfo

from celery import Task
from sqlalchemy.exc import OperationalError

from app.contenedor import ahora_utc
from app.core.config import settings
from app.documentos.dominio.errores import ArchivoInvalido
from app.documentos.dominio.puertos import ErrorAlmacen, ErrorLectura
from app.documentos.infraestructura.tareas import componentes
from app.pagos.aplicacion.pagos import AnalizarComprobante, MarcarComprobanteFallido
from app.pagos.infraestructura.cola_celery import TAREA_ANALIZAR_COMPROBANTE
from app.pagos.infraestructura.persistencia import UnidadPagosSql
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REINTENTABLES = (ErrorAlmacen, ErrorLectura, OperationalError)


def _unidad() -> UnidadPagosSql:
    c = componentes()
    return UnidadPagosSql(c.motor, c.cifrador)


def _analizar() -> AnalizarComprobante:
    c = componentes()
    return AnalizarComprobante(
        _unidad,
        ahora_utc,
        c.publicador,
        ZoneInfo(settings.timezone),
        almacen=c.almacen,
        inspector=c.inspector,
        lector=c.lector,
        revisor=c.revisor_comprobantes,
        huellero=c.cifrador,
    )


@celery_app.task(
    name=TAREA_ANALIZAR_COMPROBANTE,
    bind=True,
    acks_late=True,
    max_retries=3,
    soft_time_limit=240,
    time_limit=300,
)
def analizar_comprobante(tarea: Task, comprobante_id: str) -> str | None:
    identificador = UUID(comprobante_id)
    try:
        estado = _analizar().ejecutar(identificador)
    except REINTENTABLES as error:
        if tarea.request.retries >= (tarea.max_retries or 0):
            logger.error("El análisis del comprobante %s agotó sus reintentos", comprobante_id)
            MarcarComprobanteFallido(_unidad, ahora_utc).ejecutar(identificador)
            return None
        raise tarea.retry(exc=error, countdown=5 * 2**tarea.request.retries) from error
    except ArchivoInvalido:
        logger.warning("El comprobante %s no se pudo procesar como archivo válido", comprobante_id)
        MarcarComprobanteFallido(_unidad, ahora_utc).ejecutar(identificador)
        return None
    except Exception:
        # Un fallo que no se espera: el comprobante queda «fallido» y quien lo subió puede
        # escribir sus datos a mano, en vez de esperar para siempre.
        logger.exception("El análisis del comprobante %s falló de forma inesperada", comprobante_id)
        MarcarComprobanteFallido(_unidad, ahora_utc).ejecutar(identificador)
        return None
    return estado.value if estado else None
