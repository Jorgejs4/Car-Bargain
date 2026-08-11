"""Tasks Celery del pipeline de scraping y análisis (Fases 2-3).

- `scrape.mobile_de`: scraper -> raw HTML -> ingesta -> enqueue de imágenes.
- `download_listing_images`: imágenes del último snapshot a `raw/<source>/images/<listing_id>/`.
- `analyze_listing_images`: daño visual por foto (CLIP zero-shot) -> `photo_analyses` +
  agregación en `listing.photo_signals` + `needs_review`/`risk_score`.
- `analyze_pending_listings`: re-encola análisis para listings sin analizar (robustez).
- `update_listing_status`: marca STALE/REMOVED por ausencia (umbrales por fuente).
- Lock Redis anti-solapamiento y observabilidad mínima por ejecución.
"""

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import redis
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Listing, ListingSnapshot, ListingStatus, PhotoAnalysis
from app.schemas.photo_analysis import PhotoAnalysisResult
from app.services.ingest import ingest_listings
from app.services.listing_images import ensure_local_images
from app.services.photo_analysis import aggregate_photo_signals, evaluate_damage_risk
from app.services.raw_store import save_raw
from app.services.status import update_listing_statuses
from app.services.vision import (
    VisionUnavailableError,
    analyze_image_file,
    get_vision_analyzer,
)
from scrapers.mobile_de.scraper import MobileDeScraper
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_LOCK_KEY = "scraper:mobile_de:running"
_LAST_RUN_KEY = "scraper:mobile_de:last_run"


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


def _enqueue_analyze(listing_id: int) -> None:
    """Encola el análisis CV del listing si está habilitado."""
    if settings.cv_enabled:
        analyze_listing_images.delay(listing_id)


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

    Al terminar encola el análisis CV (`images.analyze`). Sin reintentos: los errores
    (403/404/5xx) se registran en el manifest y no bloquean al resto.
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

    result = ensure_local_images(source, source_listing_id, urls)
    logger.info(
        "images.download: listing %s (%s) -> %s descargadas, %s fallidas",
        listing_id,
        source_listing_id,
        result["downloaded"],
        result["failed"],
    )
    _enqueue_analyze(listing_id)
    return {
        "listing_id": listing_id,
        "source": source,
        "status": "done",
        "downloaded": result["downloaded"],
        "failed": result["failed"],
    }


@celery_app.task(name="images.analyze")
def analyze_listing_images(listing_id: int) -> dict:
    """Analiza las fotos del último snapshot (CLIP zero-shot) y actualiza el listing."""
    if not settings.cv_enabled:
        return {"listing_id": listing_id, "status": "cv_disabled", "analyzed": 0, "failed": 0}
    try:
        analyzer = get_vision_analyzer()
    except VisionUnavailableError as exc:
        logger.info("CV no disponible para listing %s: %s", listing_id, exc)
        return {"listing_id": listing_id, "status": "cv_unavailable", "analyzed": 0, "failed": 0}

    db = SessionLocal()
    try:
        listing = db.get(Listing, listing_id)
        if listing is None:
            return {"listing_id": listing_id, "status": "not_found", "analyzed": 0, "failed": 0}
        snapshot = _latest_snapshot(db, listing.id)
        if snapshot is None:
            return {"listing_id": listing_id, "status": "no_snapshot", "analyzed": 0, "failed": 0}
        urls = list((snapshot.raw_data or {}).get("image_urls") or [])
        source = listing.source
        source_listing_id = listing.source_listing_id
    finally:
        db.close()

    if not urls:
        return {"listing_id": listing_id, "status": "no_images", "analyzed": 0, "failed": 0}

    local = ensure_local_images(source, source_listing_id, urls)
    paths_by_url = {image["url"]: image["local_path"] for image in local["images"]}

    results_by_url: dict[str, PhotoAnalysisResult] = {}
    failed = 0
    for url, image_path in paths_by_url.items():
        try:
            results_by_url[url] = analyze_image_file(analyzer, image_path)
        except Exception as exc:  # noqa: BLE001  # un fallo de análisis no tumba al resto
            failed += 1
            logger.warning("Análisis CV fallido para %s: %s", url, exc)

    analyses = list(results_by_url.values())
    photo_signals = aggregate_photo_signals(analyses)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for url, result in results_by_url.items():
            row = db.scalar(
                select(PhotoAnalysis).where(
                    PhotoAnalysis.listing_id == listing_id,
                    PhotoAnalysis.image_url == url,
                )
            )
            if row is None:
                db.add(
                    PhotoAnalysis(
                        listing_id=listing_id,
                        image_url=url,
                        local_path=paths_by_url[url],
                        label=result.label,
                        probability=Decimal(str(result.probability)),
                        model_version=result.model_version,
                        analyzed_at=now,
                    )
                )
            else:
                row.local_path = paths_by_url[url]
                row.label = result.label
                row.probability = Decimal(str(result.probability))
                row.model_version = result.model_version
                row.analyzed_at = now

        latest = _latest_snapshot(db, listing_id)
        text_signals = latest.condition_signals if latest is not None else None
        risk, needs_review = evaluate_damage_risk(photo_signals, text_signals)

        listing = db.get(Listing, listing_id)
        if listing is not None:
            listing.photo_signals = photo_signals
            listing.risk_score = Decimal(str(risk))
            listing.needs_review = needs_review

        db.commit()
        logger.info(
            "images.analyze: listing %s -> %s fotos, %s fallidas, damage=%s, needs_review=%s",
            listing_id,
            len(analyses),
            failed,
            bool(photo_signals and photo_signals["has_visible_damage"]),
            needs_review,
        )
        return {
            "listing_id": listing_id,
            "source": source,
            "status": "done",
            "analyzed": len(analyses),
            "failed": failed,
            "has_visible_damage": bool(photo_signals and photo_signals["has_visible_damage"]),
            "needs_review": needs_review,
            "risk_score": risk,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="images.analyze_pending")
def analyze_pending_listings(limit: int = 50) -> dict:
    """Re-encola el análisis CV de listings ACTIVE sin ninguna `photo_analysis`."""
    if not settings.cv_enabled:
        return {"status": "cv_disabled", "enqueued": 0}
    try:
        get_vision_analyzer()
    except VisionUnavailableError:
        return {"status": "cv_unavailable", "enqueued": 0}

    db = SessionLocal()
    try:
        candidates = db.scalars(
            select(Listing)
            .outerjoin(PhotoAnalysis, PhotoAnalysis.listing_id == Listing.id)
            .where(Listing.status == ListingStatus.ACTIVE, PhotoAnalysis.id.is_(None))
            .limit(limit)
        ).all()
    finally:
        db.close()

    for listing in candidates:
        _enqueue_analyze(listing.id)
    logger.info("images.analyze_pending: %s listings encolados", len(candidates))
    return {"status": "enqueued", "enqueued": len(candidates)}


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
