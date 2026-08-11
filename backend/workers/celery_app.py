from app.core.config import settings
from celery import Celery

celery_app = Celery(
    "car_bargains",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["workers"])
