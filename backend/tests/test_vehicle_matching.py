"""Tests de vehicle matching (Fase 5): normalización, estrategias y traza.

Caso de aceptación: BMW 320d xDrive M Sport vs M Sportpaket → mismo vehículo.
"""

from datetime import datetime, timezone

from app.models import Vehicle, VehicleMatch
from app.services.ingest import ingest_listings
from app.services.normalization import normalize_model, normalize_variant
from scrapers.base.models import NormalizedListing
from sqlalchemy import func, select


def _nl(**overrides) -> NormalizedListing:
    data = {
        "source": "mobile_de",
        "source_listing_id": "2001",
        "url": "https://suchen.mobile.de/fahrzeuge/details.html?id=2001&vc=Car",
        "brand": "BMW",
        "model": "320d",
        "generation": "G20",
        "variant": "xDrive M Sport",
        "year": 2020,
        "mileage": 50000,
        "fuel": "diesel",
        "transmission": "automatic",
        "power_kw": 140.0,
        "price": 30000.0,
        "currency": "EUR",
        "seller_type": "dealer",
        "country": "DE",
        "title": "BMW 320d",
        "scraped_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return NormalizedListing(**data)


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def _match_for(session, source_listing_id) -> VehicleMatch:
    return session.scalar(
        select(VehicleMatch).join(VehicleMatch.listing).where(
            VehicleMatch.listing.has(source_listing_id=source_listing_id)
        )
    )


def test_normalize_model_joins_digits_and_letters() -> None:
    assert normalize_model("320 d") == "320d"
    assert normalize_model("320 d xDrive") == "320d xdrive"
    assert normalize_model("320d") == "320d"


def test_normalize_variant_canonical() -> None:
    assert normalize_variant("M Sportpaket") == "m sport"
    assert normalize_variant("M Sport") == "m sport"
    assert normalize_variant("M-Sport") == "m sport"


def test_matching_bmw_m_sport_vs_m_sportpaket(db_session) -> None:
    """Caso de aceptación: mismo vehículo a pesar de variante distinta."""
    first = _nl(source_listing_id="1", variant="xDrive M Sport")
    second = _nl(source_listing_id="2", variant="xDrive M Sportpaket")

    result = ingest_listings(db_session, [first, second])
    db_session.commit()

    assert _count(db_session, Vehicle) == 1
    assert result.listings_created == 2

    v1 = _match_for(db_session, "1")
    v2 = _match_for(db_session, "2")
    assert v1.vehicle_id == v2.vehicle_id
    assert v1.strategy == "created"
    assert v2.strategy == "exact"
    assert v2.raw_value["variant"] == "xDrive M Sportpaket"
    assert v2.normalized_value["variant"] == "xdrive m sport"


def test_matching_normalized_identity_without_variant(db_session) -> None:
    """Marca+modelo iguales pero sin variante → normalized (0.95)."""
    first = _nl(source_listing_id="1", variant=None)
    second = _nl(source_listing_id="2", variant="xDrive M Sport")

    ingest_listings(db_session, [first, second])
    db_session.commit()

    assert _count(db_session, Vehicle) == 1
    v2 = _match_for(db_session, "2")
    assert v2.strategy == "normalized"


def test_power_difference_creates_distinct_vehicle(db_session) -> None:
    """100 kW vs 150 kW no son el mismo vehículo (invariante de potencia)."""
    a = _nl(source_listing_id="1", power_kw=100.0)
    b = _nl(source_listing_id="2", power_kw=150.0)

    ingest_listings(db_session, [a, b])
    db_session.commit()

    assert _count(db_session, Vehicle) == 2
    v1 = _match_for(db_session, "1")
    v2 = _match_for(db_session, "2")
    assert v1.vehicle_id != v2.vehicle_id
    assert v1.strategy == "created"
    assert v2.strategy == "created"


def test_fuel_mismatch_creates_distinct_vehicle(db_session) -> None:
    a = _nl(source_listing_id="1", fuel="diesel")
    b = _nl(source_listing_id="2", fuel="petrol")

    ingest_listings(db_session, [a, b])
    db_session.commit()

    assert _count(db_session, Vehicle) == 2


def test_model_spelling_variants_match(db_session) -> None:
    """`320 d` vs `320d` se unifican tras normalizar."""
    a = _nl(source_listing_id="1", model="320 d")
    b = _nl(source_listing_id="2", model="320d")

    ingest_listings(db_session, [a, b])
    db_session.commit()

    assert _count(db_session, Vehicle) == 1
    assert _match_for(db_session, "2").strategy in ("exact", "normalized")


def test_trace_is_append_only_per_listing(db_session) -> None:
    """Una fila por listing: reingestar no crea filas duplicadas."""
    nl = _nl()
    ingest_listings(db_session, [nl])
    ingest_listings(db_session, [nl])
    db_session.commit()

    assert _count(db_session, VehicleMatch) == 1
