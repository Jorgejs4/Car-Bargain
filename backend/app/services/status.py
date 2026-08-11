"""Seguimiento del estado de los listings por ausencia (Fase 2).

Regla del dominio: `REMOVED != SOLD`; una desaparición de la fuente solo marca
`REMOVED`, nunca `SOLD`. Los umbrales son configurables por fuente
(`STATUS_THRESHOLDS_JSON` en `.env`), con fallback a los valores globales.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
    }
    if source:
        effective.update(_per_source_thresholds().get(source, {}))
    return effective


def update_listing_statuses(
    session: Session, *, source: str | None = None, now: datetime | None = None
) -> StatusResult:
    """Marca STALE/REMOVED según `last_seen_at`. Nunca toca SOLD ni vuelve a ACTIVE."""
    now = now or datetime.now(timezone.utc)
    result = StatusResult()
    thresholds = thresholds_for(source)
    stale_delta = timedelta(hours=thresholds["stale_after_hours"])
    removed_delta = timedelta(hours=thresholds["removed_after_hours"])

    query = select(Listing).where(Listing.status.in_([ListingStatus.ACTIVE, ListingStatus.STALE]))
    if source:
        query = query.where(Listing.source == source)

    for listing in session.scalars(query):
        if listing.last_seen_at is None:
            continue
        result.checked += 1
        age = now - listing.last_seen_at
        if age >= removed_delta:
            target = ListingStatus.REMOVED
        elif age >= stale_delta and listing.status == ListingStatus.ACTIVE:
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
