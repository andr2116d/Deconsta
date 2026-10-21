from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "deconsta",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.documentos.infraestructura.tareas", "app.pagos.infraestructura.tareas"],
)
celery_app.conf.update(
    task_default_queue="general",
    timezone=settings.timezone,
    enable_utc=True,
    # Un documento a la vez por proceso: el OCR ocupa la CPU y la memoria del worker.
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    result_expires=3600,
)
