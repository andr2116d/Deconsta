from celery import Celery

from app.core.config import settings

celery_app = Celery("deconsta", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="general",
    timezone=settings.timezone,
    enable_utc=True,
)
