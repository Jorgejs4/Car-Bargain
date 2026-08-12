from app.core.config import settings
from celery import Celery
from celery.schedules import crontab

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

celery_app.conf.beat_schedule = {
    "scrape-mobile-de-every-15m": {
        "task": "scrape.mobile_de",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"max_pages": 2},
    },
    "scrape-autoscout24-every-15m": {
        "task": "scrape.autoscout24",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"max_pages": 2},
    },
    "scrape-coches-net-every-15m": {
        "task": "scrape.coches_net",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"max_pages": 5},
    },
    "update-listing-status-every-5m": {
        "task": "status.update_listings",
        "schedule": crontab(minute="*/5"),
    },
    "analyze-pending-images-every-15m": {
        "task": "images.analyze_pending",
        "schedule": crontab(minute="*/15"),
    },
    "score-bargains-every-16m": {
        "task": "score.bargains",
        "schedule": crontab(minute="1,16,31,46"),
    },
    "import-costs-every-30m": {
        "task": "import.costs",
        "schedule": crontab(minute="*/30"),
    },
}

celery_app.autodiscover_tasks(["workers"])
