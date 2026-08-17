from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import settings
from celery import Celery
from celery.schedules import crontab


def _celery_redis_url(url: str) -> str:
    """Añade la opción TLS requerida por Upstash/Redis sobre rediss://."""
    if not url.lower().startswith("rediss://"):
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("ssl_cert_reqs", "CERT_REQUIRED")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


REDIS_URL = _celery_redis_url(settings.redis_url)

celery_app = Celery(
    "car_bargains",
    broker=REDIS_URL,
    backend=REDIS_URL,
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
    "enrich-pending-text-every-15m": {
        "task": "text.enrich_pending",
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
    "cross-border-every-32m": {
        "task": "score.cross_border",
        "schedule": crontab(minute="2,34"),
    },
    "alerts-every-35m": {
        "task": "alerts.evaluate",
        "schedule": crontab(minute="5,40"),
    },
}

if settings.scraper_scheduler.lower() == "github":
    for _scrape_schedule in (
        "scrape-mobile-de-every-15m",
        "scrape-autoscout24-every-15m",
        "scrape-coches-net-every-15m",
    ):
        celery_app.conf.beat_schedule.pop(_scrape_schedule, None)

celery_app.autodiscover_tasks(["workers"])
