"""Tasks Celery del pipeline de scraping (Fase 2).

- `scrape_mobile_de`: scraper -> raw HTML -> ingesta -> enqueue de imágenes.
- `download_listing_images`: imágenes del último snapshot a `raw/<source>/images/<listing_id>/`.
- `update_listing_status`: marca STALE/REMOVED por ausencia (umbrales por fuente).
- Lock Redis anti-solapamiento y observabilidad mínima por ejecución.
"""

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import httpx
import redis
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Listing, ListingSnapshot
from app.services.ingest import ingest_listings
from app.services.raw_store import save_image, save_manifest, save_raw
from app.services.status import update_listing_statuses
from scrapers.mobile_de.scraper import MobileDeScraper
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_LOCK_KEY = "scraper:mobile_de:running"
_LAST_RUN_KEY = "scraper:mobile_de:last_run"

_IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp", "gif", "avif"}


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def _acquire_lock() -> bool:
    """Adquiere el lock anti-solapamiento. Fail-open si Redis no está disponible."""
    try:
        acquired = _redis().set(_LOCK_KEY, "1", nx=True, ex=settings.scraper_lock_ttl_seconds)
        return bool(acquired)
    except redis.RedisError:
        logger.warning("Redis no disponible; se continúa sin lock")
        return True


def _publish_last_run(summary: dict) -> None:
    """Publica un resumen de la ejecución en Redis (observabilidad mínima). Fail-open."""
    try:
        _redis().set(_LAST_RUN_KEY, json.dumps(summary), ex=7 * 24 * 3600)
    except redis.RedisError:
        logger.warning("No se pudo publicar el resumen de ejecución en Redis")


def _latest_snapshot(session: Session, listing_id: int) -> ListingSnapshot | None:
    return session.scalar(
        select(ListingSnapshot)
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.scraped_at.desc())
        .limit(1)
    )


def _guess_extension(url: str, response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower().split("/")[-1].split(";")[0]
    if content_type in _IMAGE_SUFFIXES:
        return "jpg" if content_type == "jpeg" else content_type
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix if suffix in _IMAGE_SUFFIXES else "jpg"


def _image_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": MobileDeScraper.user_agent},
    )


@celery_app.task(
    name="scrape.mobile_de",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def scrape_mobile_de(
    max_pages: int = 1,
    save_raw_response: bool = True,
    enqueue_image_downloads: bool = True,
) -> dict:
    """Scrapea mobile.de e ingesta los anuncios. Devuelve un resumen serializable."""
    started = time.monotonic()
    if not _acquire_lock():
        logger.info("mobile_de: ya hay una ejecución en curso; se omite")
        return {"source": "mobile_de", "skipped": True, "reason": "lock"}

    scraper = MobileDeScraper()

    def _save_raw(page: int, html: str) -> None:
        if save_raw_response:
            save_raw(html, "mobile_de", f"srp_page_{page}.html")

    listings = scraper.run(max_pages=max_pages, on_page=_save_raw)

    db = SessionLocal()
    try:
        result = ingest_listings(db, listings)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if enqueue_image_downloads:
        for listing_id in result.affected_listing_ids:
            download_listing_images.delay(listing_id)

    duration_ms = int((time.monotonic() - started) * 1000)
    summary = {
        "source": "mobile_de",
        "listings": len(listings),
        "duration_ms": duration_ms,
        **asdict(result),
    }
    logger.info(
        "mobile_de: %s anuncios (%s ms) | creados=%s actualizados=%s snapshots=%s "
        "eventos=%s omitidos=%s",
        len(listings),
        duration_ms,
        result.listings_created,
        result.listings_updated,
        result.snapshots_appended,
        result.events_emitted,
        result.skipped,
    )
    _publish_last_run(summary)
    return summary


@celery_app.task(name="images.download")
def download_listing_images(listing_id: int) -> dict:
    """Descarga las imágenes del último snapshot a `raw/<source>/images/<listing_id>/`.

    Escribe un `manifest.json` con el resultado por URL. Sin reintentos: los errores
    (403/404/5xx) se registran como fallidos y no bloquean al resto.
    """
    db = SessionLocal()
    try:
        listing = db.get(Listing, listing_id)
        if listing is None:
            return {"listing_id": listing_id, "status": "not_found", "downloaded": 0, "failed": 0}
        snapshot = _latest_snapshot(db, listing.id)
        if snapshot is None:
            return {"listing_id": listing_id, "status": "no_snapshot", "downloaded": 0, "failed": 0}
        urls = list((snapshot.raw_data or {}).get("image_urls") or [])
        source = listing.source
        source_listing_id = listing.source_listing_id
    finally:
        db.close()

    if not urls:
        return {"listing_id": listing_id, "status": "no_images", "downloaded": 0, "failed": 0}

    downloaded, failed = 0, 0
    results: list[dict] = []
    with _image_client() as client:
        for index, url in enumerate(urls, start=1):
            try:
                response = client.get(url)
                response.raise_for_status()
                ext = _guess_extension(url, response)
                location = save_image(
                    response.content, source, source_listing_id, f"{index:02d}.{ext}"
                )
                if location is None:
                    raise RuntimeError("fallo al guardar la imagen")
                downloaded += 1
                results.append({"source_url": url, "local_path": location, "status": "ok"})
            except (httpx.HTTPError, RuntimeError) as exc:
                failed += 1
                results.append(
                    {"source_url": url, "local_path": None, "status": "failed", "error": str(exc)}
                )

    manifest = {
        "listing_id": listing_id,
        "source_listing_id": source_listing_id,
        "downloaded": downloaded,
        "failed": failed,
        "images": results,
    }
    save_manifest(source, source_listing_id, manifest)
    logger.info(
        "images: listing %s (%s) -> %s descargadas, %s fallidas",
        listing_id,
        source_listing_id,
        downloaded,
        failed,
    )
    return {
        "listing_id": listing_id,
        "source": source,
        "status": "done",
        "downloaded": downloaded,
        "failed": failed,
    }


@celery_app.task(name="status.update_listings")
def update_listing_status(source: str | None = None) -> dict:
    """Marca STALE/REMOVED según `last_seen_at` y los umbrales por fuente."""
    started = time.monotonic()
    db = SessionLocal()
    try:
        result = update_listing_statuses(db, source=source)
        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "status: revisados=%s stale=%s removed=%s (%s ms)",
            result.checked,
            result.stale,
            result.removed,
            duration_ms,
        )
        return {"source": source, "duration_ms": duration_ms, **asdict(result)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
