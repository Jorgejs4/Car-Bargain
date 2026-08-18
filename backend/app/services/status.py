"""Seguimiento del estado de los listings por ausencia (Fase 2).

Regla del dominio: `REMOVED != SOLD`; una desaparición de la fuente solo marca
`REMOVED`, nunca `SOLD`. Los umbrales son configurables por fuente
(`STATUS_THRESHOLDS_JSON` en `.env`), con fallback a los valores globales.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Listing, ListingEvent, ListingEventType, ListingStatus

logger = logging.getLogger(__name__)


@dataclass
class StatusResult:
    checked: int = 0
    stale: int = 0
    removed: int = 0


def _per_source_thresholds() -> dict[str, dict[str, int]]:
    raw = settings.status_thresholds_json
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        logger.warning("status_thresholds_json no es JSON válido; se ignoran umbrales por fuente")
        return {}


def thresholds_for(source: str | None) -> dict[str, int]:
    """Umbrales efectivos para una fuente: por-fuente (JSON) con fallback global."""
    effective = {
        "stale_after_hours": settings.status_stale_after_hours,
        "removed_after_hours": settings.status_removed_after_hours,
        "stale_after_misses": settings.status_stale_after_misses,
        "removed_after_misses": settings.status_removed_after_misses,
    }
    if source:
        effective.update(_per_source_thresholds().get(source, {}))
    return effective


def update_listing_statuses(
    session: Session,
    *,
    source: str | None = None,
    seen_source_listing_ids: set[str] | None = None,
    run_complete: bool = False,
    now: datetime | None = None,
) -> StatusResult:
    """Reconcilia estados solo tras una ejecución completa y fiable.

    Las ejecuciones parciales, bloqueadas o fallidas no modifican estados. La
    ausencia se acumula por ejecución completa, no por tiempo desde `last_seen_at`.
    """
    now = now or datetime.now(timezone.utc)
    result = StatusResult()
    if not run_complete or seen_source_listing_ids is None:
        logger.info("Reconciliación omitida: no hay evidencia de ejecución completa")
        return result
    thresholds = thresholds_for(source)

    query = select(Listing).where(
        Listing.status.in_([ListingStatus.ACTIVE, ListingStatus.STALE]),
        Listing.is_historical.is_(False),
    )
    if source:
        query = query.where(Listing.source == source)

    for listing in session.scalars(query):
        result.checked += 1
        if listing.source_listing_id in seen_source_listing_ids:
            listing.consecutive_misses = 0
            listing.first_missed_at = None
            listing.last_verified_at = now
            if listing.status == ListingStatus.STALE:
                old = listing.status
                listing.status = ListingStatus.ACTIVE
                session.add(ListingEvent(
                    listing_id=listing.id,
                    event_type=ListingEventType.REAPPEARED,
                    event_timestamp=now,
                    old_value={"status": old.value},
                    new_value={"status": ListingStatus.ACTIVE.value},
                ))
            continue

        listing.consecutive_misses += 1
        listing.first_missed_at = listing.first_missed_at or now
        if listing.consecutive_misses >= thresholds["removed_after_misses"]:
            target = ListingStatus.REMOVED
        elif listing.consecutive_misses >= thresholds["stale_after_misses"] and listing.status == ListingStatus.ACTIVE:
            target = ListingStatus.STALE
        else:
            continue

        old = listing.status
        listing.status = target
        if target == ListingStatus.REMOVED:
            result.removed += 1
        else:
            result.stale += 1

        session.add(
            ListingEvent(
                listing_id=listing.id,
                event_type=(
                    ListingEventType.REMOVED
                    if target == ListingStatus.REMOVED
                    else ListingEventType.STATUS_CHANGED
                ),
                event_timestamp=now,
                old_value={"status": old.value},
                new_value={"status": target.value},
            )
        )

    return result
