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
from app.engines.import_costs import estimate_for_listing
from app.engines.valuation import score_all
from app.models import Listing, ListingSnapshot, ListingStatus, PhotoAnalysis, Vehicle
from app.schemas.photo_analysis import PhotoAnalysisResult
from app.services.alerts import evaluate_alerts
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
from scrapers.autoscout24.scraper import AutoScout24Scraper
from scrapers.base.interfaces import BaseScraper
from scrapers.coches_net.scraper import CochesNetScraper
from scrapers.mobile_de.scraper import MobileDeScraper
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_LOCK_KEY_TEMPLATE = "scraper:{}:running"
_LAST_RUN_KEY_TEMPLATE = "scraper:{}:last_run"


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def _acquire_lock(source: str) -> bool:
    """Adquiere el lock anti-solapamiento por fuente. Fail-open si Redis no está disponible."""
    try:
        acquired = _redis().set(
            _LOCK_KEY_TEMPLATE.format(source), "1", nx=True, ex=settings.scraper_lock_ttl_seconds
        )
        return bool(acquired)
    except redis.RedisError:
        logger.warning("Redis no disponible; se continúa sin lock")
        return True


def _publish_last_run(summary: dict, source: str) -> None:
    """Publica un resumen de la ejecución en Redis (observabilidad mínima). Fail-open."""
    try:
        _redis().set(_LAST_RUN_KEY_TEMPLATE.format(source), json.dumps(summary), ex=7 * 24 * 3600)
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
    return _run_scrape(
        "mobile_de",
        MobileDeScraper(),
        max_pages=max_pages,
        save_raw_response=save_raw_response,
        enqueue_image_downloads=enqueue_image_downloads,
    )


@celery_app.task(
    name="scrape.autoscout24",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def scrape_autoscout24(
    max_pages: int = 1,
    save_raw_response: bool = True,
    enqueue_image_downloads: bool = True,
) -> dict:
    """Scrapea AutoScout24 en toda la UE e ingesta los anuncios."""
    return _run_scrape(
        "autoscout24",
        AutoScout24Scraper(),
        max_pages=max_pages,
        save_raw_response=save_raw_response,
        enqueue_image_downloads=enqueue_image_downloads,
        scraper_kwargs={"country_codes": ["EU"]},
    )


@celery_app.task(
    name="scrape.coches_net",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def scrape_coches_net(
    max_pages: int = 1,
    save_raw_response: bool = True,
    enqueue_image_downloads: bool = True,
) -> dict:
    """Scrapea coches.net e ingesta los anuncios."""
    return _run_scrape(
        "coches_net",
        CochesNetScraper(),
        max_pages=max_pages,
        save_raw_response=save_raw_response,
        enqueue_image_downloads=enqueue_image_downloads,
    )


def _run_scrape(
    source: str,
    scraper: BaseScraper,
    *,
    max_pages: int,
    save_raw_response: bool,
    enqueue_image_downloads: bool,
    scraper_kwargs: dict | None = None,
) -> dict:
    """Ejecuta un scraper genérico: lock → fetch → ingesta → imágenes → resumen."""
    started = time.monotonic()
    if not _acquire_lock(source):
        logger.info("%s: ya hay una ejecución en curso; se omite", source)
        return {"source": source, "skipped": True, "reason": "lock"}

    def _save_raw(page: int, html: str) -> None:
        if save_raw_response:
            save_raw(html, source, f"srp_page_{page}.html")

    listings = scraper.run(max_pages=max_pages, on_page=_save_raw, **(scraper_kwargs or {}))

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
        for listing_id in result.changed_listing_ids:
            download_listing_images.delay(listing_id)

    duration_ms = int((time.monotonic() - started) * 1000)
    summary = {
        "source": source,
        "listings": len(listings),
        "duration_ms": duration_ms,
        **asdict(result),
    }
    logger.info(
        "%s: %s anuncios (%s ms) | creados=%s actualizados=%s snapshots=%s "
        "eventos=%s omitidos=%s",
        source,
        len(listings),
        duration_ms,
        result.listings_created,
        result.listings_updated,
        result.snapshots_appended,
        result.events_emitted,
        result.skipped,
    )
    _publish_last_run(summary, source)
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

    # Fase 3: pre-filtro de escena. Solo las fotos exteriores pasan al detector
    # de daños; las interiores, motor y otras se guardan con la escena detectada.
    damage_results: dict[str, PhotoAnalysisResult] = {}
    scene_results: dict[str, str] = {}
    skipped_scenes = 0
    failed = 0

    for url, image_path in paths_by_url.items():
        try:
            # Primero clasificar escena (exterior/interior/motor/otro)
            scene, _scene_prob = analyzer.classify_scene(image_path)

            if scene == "exterior":
                # Solo exteriores → detector de daños
                damage_results[url] = analyze_image_file(analyzer, image_path)
            else:
                scene_results[url] = scene
                skipped_scenes += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning("Análisis CV fallido para %s: %s", url, exc)

    analyses = list(damage_results.values())
    photo_signals = aggregate_photo_signals(analyses)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        def _upsert_analysis(url: str, label: str, prob: float) -> None:
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
                        label=label,
                        probability=Decimal(str(prob)),
                        model_version=analyzer.model_version,
                        analyzed_at=now,
                    )
                )
            else:
                row.local_path = paths_by_url[url]
                row.label = label
                row.probability = Decimal(str(prob))
                row.model_version = analyzer.model_version
                row.analyzed_at = now

        for url, result in damage_results.items():
            _upsert_analysis(url, result.label, result.probability)

        for url, scene in scene_results.items():
            _upsert_analysis(url, f"escena_{scene}", 1.0)

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
            "images.analyze: listing %s -> %s fotos exterior, %s escenas saltadas, %s fallidas, damage=%s, needs_review=%s",
            listing_id,
            len(analyses),
            skipped_scenes,
            failed,
            bool(photo_signals and photo_signals["has_visible_damage"]),
            needs_review,
        )
        return {
            "listing_id": listing_id,
            "source": source,
            "status": "done",
            "analyzed": len(analyses),
            "skipped_scenes": skipped_scenes,
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
            .where(
                Listing.status == ListingStatus.ACTIVE,
                Listing.is_historical.is_(False),
                PhotoAnalysis.id.is_(None),
            )
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


@celery_app.task(name="score.bargains")
def score_bargains() -> dict:
    """Calcula `bargain_score` con el motor de valoración (Fase 6).

    Entrena un modelo de regresión lineal multivariable con todos los listings
    ACTIVE no históricos (año, km, combustible, cambio, marca, daños CV) y
    predice el precio justo de cada uno.

    bargain_score = (precio_predicho - precio_real) / precio_predicho.
    Positivo → el coche está más barato de lo esperado → posible ganga.
    """
    started = time.monotonic()
    db = SessionLocal()
    try:
        result = score_all(db)
        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "score.bargains: %s puntuados, R²=%s (%s ms)",
            result.get("scored"),
            result.get("r2"),
            duration_ms,
        )
        return {"duration_ms": duration_ms, **result}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="import.costs")
def compute_import_costs() -> dict:
    """Calcula el coste de importación a España para listings no-ES.

    Para cada listing ACTIVE no histórico con país != ES: estima impuesto
    de matriculación, transporte, ITV y gestoría, y guarda el total.
    """
    started = time.monotonic()
    db = SessionLocal()
    try:
        listings = db.scalars(
            select(Listing).where(
                Listing.status == ListingStatus.ACTIVE,
                Listing.is_historical.is_(False),
                Listing.country != "ES",
            )
        ).all()

        computed = 0
        for li in listings:
            snap = db.scalar(
                select(ListingSnapshot)
                .where(ListingSnapshot.listing_id == li.id)
                .order_by(ListingSnapshot.scraped_at.desc())
                .limit(1)
            )
            if snap is None or snap.price is None:
                continue

            vehicle = db.get(Vehicle, li.vehicle_id) if li.vehicle_id else None
            co2 = vehicle.co2_g_km if vehicle else None

            estimate = estimate_for_listing(
                source_country=li.country or "DE",
                price_eur=float(snap.price),
                co2_g_km=co2,
            )

            li.estimated_import_cost = estimate.total_import_cost
            li.total_cost_es = float(snap.price) + estimate.total_import_cost
            computed += 1

        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("import.costs: %s listings (%s ms)", computed, duration_ms)
        return {"computed": computed, "duration_ms": duration_ms}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="score.cross_border")
def score_cross_border() -> dict:
    """Fase 9: margen cross-border descontando costes de importación.

    Para cada listing ACTIVE no histórico:
      cross_border_margin = absolute_margin - estimated_import_cost
      cross_border_score  = cross_border_margin / predicted_price

    Un cross_border_margin positivo significa que incluso después de pagar
    la importación, el coche sigue por debajo del valor de mercado predicho.
    """
    started = time.monotonic()
    db = SessionLocal()
    try:
        listings = db.scalars(
            select(Listing).where(
                Listing.status == ListingStatus.ACTIVE,
                Listing.is_historical.is_(False),
            )
        ).all()

        scored = 0
        for li in listings:
            am = li.absolute_margin
            pp = li.predicted_price
            imp = li.estimated_import_cost or 0.0
            if am is None or pp is None or pp == 0:
                continue

            cbm = am - imp
            li.cross_border_margin = round(cbm, 2)
            li.cross_border_score = round(cbm / pp, 6)
            scored += 1

        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("score.cross_border: %s listings (%s ms)", scored, duration_ms)
        return {"scored": scored, "duration_ms": duration_ms}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="alerts.evaluate")
def evaluate_alerts_task() -> dict:
    """Fase 10: genera notificaciones para listings que cumplen las preferencias."""
    started = time.monotonic()
    db = SessionLocal()
    try:
        result = evaluate_alerts(db)
        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "alerts.evaluate: revisados=%s matched=%s notificados=%s dedup=%s (%s ms)",
            result.checked,
            result.matched,
            result.notified,
            result.deduped,
            duration_ms,
        )
        return {
            "checked": result.checked,
            "matched": result.matched,
            "notified": result.notified,
            "deduped": result.deduped,
            "duration_ms": duration_ms,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
