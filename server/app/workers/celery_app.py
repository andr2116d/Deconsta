from celery import Celery

from app.core.config import settings

celery_app = Celery("control_de_pagos", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="general",
    timezone=settings.timezone,
    enable_utc=True,
)
