"""Ingesta de `NormalizedListing` en la base de datos (Fase 2).

- Upsert de listings por identidad `(source, source_listing_id)`.
- `find_or_create_vehicle` con clave exacta amplia (matching fino = Fase 4).
- Snapshots SIEMPRE append-only (nunca sobrescribir).
- `condition_signals` de texto (lexicón DE/ES) en cada snapshot, con `confidence`+`source`.
- Emite eventos `LISTED`, `PRICE_CHANGED`, `MILEAGE_CHANGED`, `DESCRIPTION_CHANGED`, `REAPPEARED`.

El commit lo decide el llamador (task Celery / script); aquí solo se flushea.
"""

import logging
from dataclasses import dataclass, field

from scrapers.base.condition import extract_condition_signals
from scrapers.base.models import NormalizedListing
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Listing,
    ListingEvent,
    ListingEventType,
    ListingSnapshot,
    ListingStatus,
    Vehicle,
)

logger = logging.getLogger(__name__)

_POWER_TOLERANCE = 0.001

# Idioma del lexicón según el país del anuncio (default alemán, el idioma dominante).
_LANG_BY_COUNTRY = {"DE": "de", "AT": "de", "CH": "de", "ES": "es"}


def _language_for(nl: NormalizedListing) -> str:
    return _LANG_BY_COUNTRY.get((nl.country or "").upper(), "de")


def _condition_signals_for(nl: NormalizedListing) -> dict:
    text = " ".join(part for part in (nl.title, nl.description) if part)
    return extract_condition_signals(text, lang=_language_for(nl), source="listing_text")


@dataclass
class IngestResult:
    listings_created: int = 0
    listings_updated: int = 0
    snapshots_appended: int = 0
    events_emitted: int = 0
    skipped: int = 0
    # Ids de los listings creados o actualizados en esta ejecución (para tareas posteriores).
    affected_listing_ids: list[int] = field(default_factory=list)


def find_or_create_vehicle(session: Session, nl: NormalizedListing) -> Vehicle:
    candidates = session.scalars(
        select(Vehicle).where(
            Vehicle.brand == nl.brand,
            Vehicle.model == nl.model,
            Vehicle.generation == nl.generation,
            Vehicle.variant == nl.variant,
            Vehicle.year == nl.year,
            Vehicle.fuel == nl.fuel,
            Vehicle.transmission == nl.transmission,
        )
    ).all()
    for vehicle in candidates:
        if (vehicle.power_kw is None and nl.power_kw is None) or (
            vehicle.power_kw is not None
            and nl.power_kw is not None
            and abs(float(vehicle.power_kw) - nl.power_kw) < _POWER_TOLERANCE
        ):
            return vehicle
    vehicle = Vehicle(
        brand=nl.brand,
        model=nl.model,
        generation=nl.generation,
        variant=nl.variant,
        year=nl.year,
        fuel=nl.fuel,
        transmission=nl.transmission,
        power_kw=nl.power_kw,
        co2_g_km=nl.co2_g_km,
    )
    session.add(vehicle)
    session.flush()
    return vehicle


def upsert_listing(session: Session, nl: NormalizedListing) -> tuple[Listing, bool, bool]:
    """Crea o actualiza un listing. Devuelve `(listing, created, was_removed)`."""
    listing = session.scalar(
        select(Listing).where(
            Listing.source == nl.source,
            Listing.source_listing_id == nl.source_listing_id,
        )
    )
    if listing is None:
        listing = Listing(
            source=nl.source,
            source_listing_id=nl.source_listing_id,
            url=nl.url,
            seller_type=nl.seller_type,
            country=nl.country,
            first_seen_at=nl.scraped_at,
            last_seen_at=nl.scraped_at,
            status=ListingStatus.ACTIVE,
        )
        session.add(listing)
        session.flush()
        return listing, True, False

    was_removed = listing.status == ListingStatus.REMOVED
    listing.url = nl.url
    listing.seller_type = nl.seller_type
    listing.country = nl.country
    listing.last_seen_at = nl.scraped_at
    if was_removed:
        listing.status = ListingStatus.ACTIVE
    return listing, False, was_removed


def _latest_snapshot(session: Session, listing_id: int) -> ListingSnapshot | None:
    return session.scalar(
        select(ListingSnapshot)
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.scraped_at.desc())
        .limit(1)
    )


def _append_snapshot(session: Session, listing: Listing, nl: NormalizedListing) -> None:
    session.add(
        ListingSnapshot(
            listing_id=listing.id,
            scraped_at=nl.scraped_at,
            price=nl.price,
            currency=nl.currency,
            mileage=nl.mileage,
            title=nl.title,
            description=nl.description,
            seller_type=nl.seller_type,
            location=nl.city,
            condition_signals=_condition_signals_for(nl),
            raw_data=nl.model_dump(mode="json"),
        )
    )


def _emit_events(
    session: Session,
    listing: Listing,
    nl: NormalizedListing,
    prev_snapshot: ListingSnapshot | None,
    *,
    created: bool,
    was_removed: bool,
) -> int:
    events: list[tuple[ListingEventType, dict | None, dict | None]] = []
    if was_removed:
        events.append((ListingEventType.REAPPEARED, None, {"status": ListingStatus.ACTIVE.value}))
    elif created:
        events.append((ListingEventType.LISTED, None, {"price": str(nl.price)}))
    elif prev_snapshot is not None:
        if prev_snapshot.price != nl.price:
            events.append(
                (
                    ListingEventType.PRICE_CHANGED,
                    {"price": str(prev_snapshot.price)},
                    {"price": str(nl.price)},
                )
            )
        if prev_snapshot.mileage != nl.mileage and nl.mileage is not None and prev_snapshot.mileage is not None:
            events.append(
                (
                    ListingEventType.MILEAGE_CHANGED,
                    {"mileage": prev_snapshot.mileage},
                    {"mileage": nl.mileage},
                )
            )
        if (prev_snapshot.title, prev_snapshot.description) != (nl.title, nl.description):
            events.append(
                (
                    ListingEventType.DESCRIPTION_CHANGED,
                    {"title": prev_snapshot.title, "description": prev_snapshot.description},
                    {"title": nl.title, "description": nl.description},
                )
            )
    for event_type, old_value, new_value in events:
        session.add(
            ListingEvent(
                listing_id=listing.id,
                event_type=event_type,
                event_timestamp=nl.scraped_at,
                old_value=old_value,
                new_value=new_value,
            )
        )
    return len(events)


def _ingest_one(session: Session, nl: NormalizedListing) -> tuple[Listing, bool, bool, int]:
    """Ingesta un anuncio. Devuelve `(listing, created, was_removed, events)`."""
    listing, created, was_removed = upsert_listing(session, nl)
    vehicle = find_or_create_vehicle(session, nl)
    listing.vehicle_id = vehicle.id
    prev_snapshot = _latest_snapshot(session, listing.id)
    _append_snapshot(session, listing, nl)
    events = _emit_events(session, listing, nl, prev_snapshot, created=created, was_removed=was_removed)
    return listing, created, was_removed, events


def ingest_listings(session: Session, listings: list[NormalizedListing]) -> IngestResult:
    result = IngestResult()
    for nl in listings:
        try:
            with session.begin_nested():
                listing, created, was_removed, events = _ingest_one(session, nl)
        except Exception:
            logger.exception("Fallo al ingestar anuncio %s/%s", nl.source, nl.source_listing_id)
            result.skipped += 1
            continue
        if created:
            result.listings_created += 1
        elif was_removed:
            result.listings_updated += 1
        else:
            result.listings_updated += 1
        result.affected_listing_ids.append(listing.id)
        result.snapshots_appended += 1
        result.events_emitted += events
    return result
