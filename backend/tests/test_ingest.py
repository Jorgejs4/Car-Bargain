from datetime import datetime, timedelta, timezone

from app.models import (
    Listing,
    ListingEvent,
    ListingEventType,
    ListingSnapshot,
    ListingStatus,
    Vehicle,
)
from app.services.ingest import ingest_listings
from scrapers.base.models import NormalizedListing
from sqlalchemy import func, select


def _make_nl(**overrides) -> NormalizedListing:
    data = {
        "source": "mobile_de",
        "source_listing_id": "1001",
        "url": "https://suchen.mobile.de/fahrzeuge/details.html?id=1001&vc=Car",
        "brand": "Volkswagen",
        "model": "Golf",
        "year": 2013,
        "mileage": 100000,
        "fuel": "petrol",
        "transmission": "manual",
        "power_kw": 100.0,
        "price": 12000.0,
        "currency": "EUR",
        "seller_type": "dealer",
        "country": "DE",
        "city": "Berlin",
        "title": "VW Golf GTI",
        "scraped_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return NormalizedListing(**data)


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_ingest_creates_listing_vehicle_snapshot_and_listed_event(db_session) -> None:
    nl = _make_nl()
    result = ingest_listings(db_session, [nl])
    db_session.commit()

    assert result.listings_created == 1
    assert result.snapshots_appended == 1
    assert result.events_emitted == 1
    assert result.skipped == 0

    listing = db_session.scalar(select(Listing).where(Listing.source == "mobile_de"))
    assert listing is not None
    assert listing.source_listing_id == "1001"
    assert listing.status == ListingStatus.ACTIVE
    assert listing.first_seen_at == nl.scraped_at
    assert listing.vehicle_id is not None

    vehicle = db_session.get(Vehicle, listing.vehicle_id)
    assert vehicle.brand == "Volkswagen"
    assert vehicle.model == "Golf"

    snapshot = db_session.scalar(select(ListingSnapshot))
    assert snapshot.price == nl.price
    assert snapshot.raw_data["source_listing_id"] == "1001"

    event = db_session.scalar(select(ListingEvent))
    assert event.event_type == ListingEventType.LISTED


def test_ingest_is_idempotent_and_snapshots_are_append_only(db_session) -> None:
    first = _make_nl(scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc), price=12000.0)
    second = _make_nl(scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc), price=11500.0)

    ingest_listings(db_session, [first])
    result = ingest_listings(db_session, [second])
    db_session.commit()

    assert result.listings_created == 0
    assert result.listings_updated == 1
    assert _count(db_session, Listing) == 1
    assert _count(db_session, Vehicle) == 1
    assert _count(db_session, ListingSnapshot) == 2

    snapshots = db_session.scalars(select(ListingSnapshot).order_by(ListingSnapshot.scraped_at)).all()
    assert {float(s.price) for s in snapshots} == {12000.0, 11500.0}

    events = db_session.scalars(select(ListingEvent)).all()
    assert [e.event_type for e in events] == [ListingEventType.LISTED, ListingEventType.PRICE_CHANGED]


def test_ingest_without_price_change_emits_no_price_event(db_session) -> None:
    first = _make_nl(scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc), price=12000.0)
    second = _make_nl(scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc), price=12000.0)
    ingest_listings(db_session, [first])
    ingest_listings(db_session, [second])
    db_session.commit()
    assert _count(db_session, ListingEvent) == 1


def test_ingest_emits_mileage_change_event(db_session) -> None:
    first = _make_nl(scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc), mileage=100000)
    second = _make_nl(scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc), mileage=101000)
    ingest_listings(db_session, [first])
    ingest_listings(db_session, [second])
    db_session.commit()

    types = db_session.scalars(select(ListingEvent.event_type)).all()
    assert ListingEventType.MILEAGE_CHANGED in types


def test_reappeared_removed_listing_is_reactivated(db_session) -> None:
    removed = Listing(
        source="mobile_de",
        source_listing_id="1001",
        first_seen_at=datetime.now(timezone.utc),
        status=ListingStatus.REMOVED,
    )
    db_session.add(removed)
    db_session.commit()

    result = ingest_listings(db_session, [_make_nl()])
    db_session.commit()

    listing = db_session.scalar(select(Listing).where(Listing.source == "mobile_de"))
    assert listing.status == ListingStatus.ACTIVE
    assert result.listings_updated == 1

    event = db_session.scalar(select(ListingEvent).order_by(ListingEvent.id.desc()))
    assert event.event_type == ListingEventType.REAPPEARED


def test_stale_listing_is_reactivated_with_status_changed_event(db_session) -> None:
    stale = Listing(
        source="mobile_de",
        source_listing_id="1001",
        first_seen_at=datetime.now(timezone.utc),
        status=ListingStatus.STALE,
    )
    db_session.add(stale)
    db_session.commit()

    result = ingest_listings(db_session, [_make_nl()])
    db_session.commit()

    listing = db_session.scalar(select(Listing).where(Listing.source == "mobile_de"))
    assert listing.status == ListingStatus.ACTIVE
    assert result.listings_updated == 1

    event = db_session.scalar(select(ListingEvent).order_by(ListingEvent.id.desc()))
    assert event.event_type == ListingEventType.STATUS_CHANGED
    assert event.old_value == {"status": "STALE"}
    assert event.new_value == {"status": "ACTIVE"}


def test_sold_listing_is_not_reactivated_by_reappearance(db_session) -> None:
    sold = Listing(
        source="mobile_de",
        source_listing_id="1001",
        first_seen_at=datetime.now(timezone.utc),
        status=ListingStatus.SOLD,
    )
    db_session.add(sold)
    db_session.commit()

    ingest_listings(db_session, [_make_nl()])
    db_session.commit()

    listing = db_session.scalar(select(Listing).where(Listing.source == "mobile_de"))
    assert listing.status == ListingStatus.SOLD


def test_vehicle_shared_by_same_key_and_distinct_by_power(db_session) -> None:
    a = _make_nl(source_listing_id="1", power_kw=100.0)
    b = _make_nl(source_listing_id="2", power_kw=100.0)
    c = _make_nl(source_listing_id="3", power_kw=150.0)

    ingest_listings(db_session, [a, b, c])
    db_session.commit()

    assert _count(db_session, Vehicle) == 2

    id_a = db_session.scalar(select(Listing.vehicle_id).where(Listing.source_listing_id == "1"))
    id_b = db_session.scalar(select(Listing.vehicle_id).where(Listing.source_listing_id == "2"))
    id_c = db_session.scalar(select(Listing.vehicle_id).where(Listing.source_listing_id == "3"))
    assert id_a == id_b
    assert id_c != id_a


def test_ingest_skips_only_the_bad_listing(db_session) -> None:
    good_1 = _make_nl(source_listing_id="1", scraped_at=datetime.now(timezone.utc))
    bad = _make_nl(source_listing_id="2", brand="V" * 200, scraped_at=datetime.now(timezone.utc))
    good_2 = _make_nl(source_listing_id="3", scraped_at=datetime.now(timezone.utc) + timedelta(minutes=1))

    result = ingest_listings(db_session, [good_1, bad, good_2])
    db_session.commit()

    assert result.skipped == 1
    assert result.listings_created == 2
    assert _count(db_session, Listing) == 2
    assert _count(db_session, ListingSnapshot) == 2


def test_snapshot_includes_condition_signals_from_text(db_session) -> None:
    nl = _make_nl(description="Unfallwagen, Motorschaden, Rost am Heck, Kratzer")
    ingest_listings(db_session, [nl])
    db_session.commit()

    snapshot = db_session.scalar(select(ListingSnapshot))
    signals = snapshot.condition_signals
    assert signals is not None
    assert signals["has_accident"] is True
    assert signals["has_engine_issue"] is True
    assert signals["has_rust"] is True
    assert signals["has_cosmetic_damage"] is True
    assert signals["source"] == "listing_text"
    assert signals["confidence"] > 0
    assert "Unfallwagen" in signals["keywords_found"]


def test_snapshot_condition_signals_unknown_when_no_evidence(db_session) -> None:
    nl = _make_nl(title="VW Golf GTI", description="TÜV neu, Sommerreifen, Klima")
    ingest_listings(db_session, [nl])
    db_session.commit()

    signals = db_session.scalar(select(ListingSnapshot)).condition_signals
    assert signals["accident_free"] is False
    assert signals["has_accident"] is False
    assert signals["text_contradiction"] is False


def test_ingest_emits_description_changed_event(db_session) -> None:
    first = _make_nl(scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc), description="Primera versión")
    second = _make_nl(
        scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc), description="Versión editada por el vendedor"
    )
    ingest_listings(db_session, [first])
    result = ingest_listings(db_session, [second])
    db_session.commit()

    types = db_session.scalars(select(ListingEvent.event_type)).all()
    assert types == [ListingEventType.LISTED, ListingEventType.DESCRIPTION_CHANGED]
    assert result.events_emitted == 1


def test_no_description_changed_event_when_unchanged(db_session) -> None:
    first = _make_nl(scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc), title="Título fijo")
    second = _make_nl(scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc), title="Título fijo")
    ingest_listings(db_session, [first])
    ingest_listings(db_session, [second])
    db_session.commit()
    assert _count(db_session, ListingEvent) == 1


def test_ingest_collects_affected_listing_ids(db_session) -> None:
    a = _make_nl(source_listing_id="1", scraped_at=datetime.now(timezone.utc))
    b = _make_nl(source_listing_id="2", scraped_at=datetime.now(timezone.utc))
    result = ingest_listings(db_session, [a, b])
    db_session.commit()

    assert len(result.affected_listing_ids) == 2
    assert len(set(result.affected_listing_ids)) == 2


def test_ingest_changed_listing_ids_new_listings(db_session) -> None:
    result = ingest_listings(db_session, [_make_nl()])
    db_session.commit()
    assert len(result.changed_listing_ids) == 1


def test_ingest_changed_listing_ids_empty_when_identical(db_session) -> None:
    first = _make_nl(
        source_listing_id="1", scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        image_urls=["https://img.example/1.jpg"],
    )
    second = _make_nl(
        source_listing_id="1", scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        image_urls=["https://img.example/1.jpg"],
    )
    ingest_listings(db_session, [first])
    result = ingest_listings(db_session, [second])
    db_session.commit()
    assert len(result.affected_listing_ids) == 1
    assert result.changed_listing_ids == []


def test_ingest_changed_listing_ids_on_image_change(db_session) -> None:
    first = _make_nl(
        source_listing_id="1", scraped_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        image_urls=["https://img.example/1.jpg"],
    )
    second = _make_nl(
        source_listing_id="1", scraped_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        image_urls=["https://img.example/1.jpg", "https://img.example/2.jpg"],
    )
    ingest_listings(db_session, [first])
    result = ingest_listings(db_session, [second])
    db_session.commit()
    assert len(result.changed_listing_ids) == 1


def test_ingest_changed_listing_ids_on_stale_reactivation(db_session) -> None:
    stale = Listing(
        source="mobile_de",
        source_listing_id="1001",
        first_seen_at=datetime.now(timezone.utc),
        status=ListingStatus.STALE,
    )
    db_session.add(stale)
    db_session.commit()

    result = ingest_listings(db_session, [_make_nl()])
    db_session.commit()
    assert len(result.changed_listing_ids) == 1
