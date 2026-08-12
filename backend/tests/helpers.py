"""Helpers de seeding para tests de la API (Fase 4).

El fixture `committed_session` está en `conftest.py`.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models import Listing, ListingSnapshot, ListingStatus, Vehicle


def make_vehicle(
    db,
    *,
    brand="BMW",
    model="320d",
    year=2019,
    fuel="diesel",
    transmission="automatic",
    power_kw=135,
):
    vehicle = Vehicle(
        brand=brand,
        model=model,
        year=year,
        fuel=fuel,
        transmission=transmission,
        power_kw=power_kw,
    )
    db.add(vehicle)
    db.flush()
    return vehicle


def make_listing(
    db,
    *,
    vehicle,
    source="mobile_de",
    source_listing_id=None,
    country="DE",
    status=ListingStatus.ACTIVE,
    is_historical=False,
    needs_review=False,
    photo_signals=None,
    risk_score=None,
):
    source_listing_id = source_listing_id or str(uuid4())
    listing = Listing(
        source=source,
        source_listing_id=source_listing_id,
        vehicle_id=vehicle.id,
        country=country,
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=1),
        last_seen_at=datetime.now(timezone.utc),
        status=status,
        is_historical=is_historical,
        needs_review=needs_review,
        photo_signals=photo_signals,
        risk_score=risk_score,
        url=f"https://s.example/{source_listing_id}",
        seller_type="dealer",
    )
    db.add(listing)
    db.flush()
    return listing


def make_snapshot(
    db,
    listing,
    *,
    price=10000,
    currency="EUR",
    mileage=50000,
    title="Titulo",
    condition_signals=None,
    scraped_at=None,
):
    snapshot = ListingSnapshot(
        listing_id=listing.id,
        scraped_at=scraped_at or datetime.now(timezone.utc),
        price=Decimal(str(price)),
        currency=currency,
        mileage=mileage,
        title=title,
        condition_signals=condition_signals,
    )
    db.add(snapshot)
    db.flush()
    return snapshot
