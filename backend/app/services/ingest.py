"""Ingesta de `NormalizedListing` en la base de datos (Fase 2).

- Upsert de listings por identidad `(source, source_listing_id)`.
- Vehicle matching normalizado (Fase 5): `match_vehicle` asigna/crea el vehículo
  y conserva la traza en `vehicle_matches`.
- Snapshots SIEMPRE append-only (nunca sobrescribir).
- `condition_signals` de texto (lexicón DE/ES) en cada snapshot, con `confidence`+`source`.
- Emite eventos `LISTED`, `PRICE_CHANGED`, `MILEAGE_CHANGED`, `DESCRIPTION_CHANGED`, `REAPPEARED`, `STATUS_CHANGED`.

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
    VehicleMatch,
)
from app.services.vehicle_matching import match_vehicle

logger = logging.getLogger(__name__)

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
    # Ids de listings nuevos o con cambios reales (precio/km/título/imágenes/estado).
    # Los ya vistos e idénticos no entran aquí: se saltan descarga de imágenes y CV.
    changed_listing_ids: list[int] = field(default_factory=list)


def upsert_listing(session: Session, nl: NormalizedListing) -> tuple[Listing, bool, ListingStatus | None]:
    """Crea o actualiza un listing. Devuelve `(listing, created, prev_status)`.

    `prev_status` es el estado previo si el listing ya existía (`None` si es
    nuevo). Reaparecer desde `STALE` o `REMOVED` reactiva a `ACTIVE`; desde
    `SOLD` no (la venta es terminal y requiere intervención manual).
    """
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
        return listing, True, None

    prev_status = listing.status
    listing.url = nl.url
    listing.seller_type = nl.seller_type
    listing.country = nl.country
    listing.last_seen_at = nl.scraped_at
    if prev_status in (ListingStatus.REMOVED, ListingStatus.STALE):
        listing.status = ListingStatus.ACTIVE
    return listing, False, prev_status


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


def _image_urls_changed(prev_snapshot: ListingSnapshot | None, nl: NormalizedListing) -> bool:
    """True si la lista de imágenes del snapshot previo difiere de la actual."""
    if prev_snapshot is None:
        return False
    prev_urls = set((prev_snapshot.raw_data or {}).get("image_urls") or [])
    return set(nl.image_urls) != prev_urls


def _emit_events(
    session: Session,
    listing: Listing,
    nl: NormalizedListing,
    prev_snapshot: ListingSnapshot | None,
    *,
    created: bool,
    prev_status: ListingStatus | None,
) -> int:
    events: list[tuple[ListingEventType, dict | None, dict | None]] = []
    if prev_status == ListingStatus.REMOVED:
        events.append((ListingEventType.REAPPEARED, None, {"status": ListingStatus.ACTIVE.value}))
    elif prev_status == ListingStatus.STALE:
        events.append(
            (
                ListingEventType.STATUS_CHANGED,
                {"status": ListingStatus.STALE.value},
                {"status": ListingStatus.ACTIVE.value},
            )
        )
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


def _record_match(session: Session, listing: Listing, result, nl: NormalizedListing) -> None:
    """Upsert de la traza de matching en `vehicle_matches` (una fila por listing)."""
    match = session.scalar(select(VehicleMatch).where(VehicleMatch.listing_id == listing.id))
    if match is None:
        match = VehicleMatch(listing_id=listing.id)
        session.add(match)
    match.vehicle_id = result.vehicle.id
    match.strategy = result.strategy
    match.confidence = result.confidence
    match.normalized_value = result.normalized_value
    match.raw_value = {
        "brand": nl.brand,
        "model": nl.model,
        "generation": nl.generation,
        "variant": nl.variant,
        "fuel": nl.fuel,
        "transmission": nl.transmission,
    }
    match.source = "vehicle_matching"
    session.flush()


def _ingest_one(session: Session, nl: NormalizedListing) -> tuple[Listing, bool, ListingStatus | None, int, bool]:
    """Ingesta un anuncio. Devuelve `(listing, created, prev_status, events, changed)`."""
    listing, created, prev_status = upsert_listing(session, nl)
    result = match_vehicle(session, nl)
    listing.vehicle_id = result.vehicle.id
    _record_match(session, listing, result, nl)
    prev_snapshot = _latest_snapshot(session, listing.id)
    _append_snapshot(session, listing, nl)
    events = _emit_events(
        session, listing, nl, prev_snapshot, created=created, prev_status=prev_status
    )
    changed = (
        created
        or prev_status in (ListingStatus.REMOVED, ListingStatus.STALE)
        or events > 0
        or _image_urls_changed(prev_snapshot, nl)
    )
    return listing, created, prev_status, events, changed


def ingest_listings(session: Session, listings: list[NormalizedListing]) -> IngestResult:
    result = IngestResult()
    for nl in listings:
        try:
            with session.begin_nested():
                listing, created, _prev_status, events, changed = _ingest_one(session, nl)
        except Exception:
            logger.exception("Fallo al ingestar anuncio %s/%s", nl.source, nl.source_listing_id)
            result.skipped += 1
            continue
        if created:
            result.listings_created += 1
        else:
            result.listings_updated += 1
        result.affected_listing_ids.append(listing.id)
        if changed:
            result.changed_listing_ids.append(listing.id)
        result.snapshots_appended += 1
        result.events_emitted += events
    return result
