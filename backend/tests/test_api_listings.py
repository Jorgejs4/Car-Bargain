"""Tests de la API REST de listings (Fase 4)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.main import app
from app.models import ListingEvent, ListingEventType, ListingSnapshot, ListingStatus
from fastapi.testclient import TestClient

from tests import helpers

client = TestClient(app)


def _seed_one(db, **kwargs):
    vehicle = helpers.make_vehicle(db, **kwargs.pop("vehicle_kwargs", {}))
    listing = helpers.make_listing(db, vehicle=vehicle, **kwargs.pop("listing_kwargs", {}))
    helpers.make_snapshot(db, listing, **kwargs.pop("snapshot_kwargs", {}))
    db.commit()
    return vehicle, listing


def test_listings_defaults_to_active_and_exposes_signals(committed_session) -> None:
    _, l = _seed_one(
        committed_session,
        snapshot_kwargs={
            "price": 15900,
            "mileage": 80000,
            "title": "BMW 320d",
            "condition_signals": {"accident_free": True},
        },
        listing_kwargs={
            "needs_review": True,
            "photo_signals": {"has_visible_damage": True, "damage_types": ["abolladura"]},
            "risk_score": Decimal("0.55"),
        },
    )
    _seed_one(
        committed_session,
        listing_kwargs={"source_listing_id": "L2", "status": ListingStatus.REMOVED},
        vehicle_kwargs={"brand": "Audi", "model": "A4", "year": 2021, "fuel": "petrol"},
        snapshot_kwargs={"price": 30000},
    )

    response = client.get("/api/v1/listings")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == l.id
    assert item["brand"] == "BMW"
    assert item["model"] == "320d"
    assert item["year"] == 2019
    assert item["price"] == 15900.0
    assert item["mileage"] == 80000
    assert item["title"] == "BMW 320d"
    assert item["status"] == "ACTIVE"
    assert item["condition_signals"] == {"accident_free": True}
    assert item["photo_signals"]["has_visible_damage"] is True
    assert item["needs_review"] is True
    assert item["risk_score"] == 0.55


def test_listings_active_endpoint_only_active(committed_session) -> None:
    _seed_one(committed_session, listing_kwargs={"source_listing_id": "L1", "status": ListingStatus.ACTIVE})
    _seed_one(
        committed_session,
        listing_kwargs={"source_listing_id": "L2", "status": ListingStatus.STALE},
        vehicle_kwargs={"brand": "Audi", "model": "A4"},
    )
    response = client.get("/api/v1/listings/active")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["source_listing_id"] == "L1"


def test_listings_filters(committed_session) -> None:
    _seed_one(
        committed_session,
        listing_kwargs={"source_listing_id": "L1"},
        snapshot_kwargs={"price": 15900, "mileage": 80000},
    )
    _seed_one(
        committed_session,
        vehicle_kwargs={"brand": "Audi", "model": "A4", "year": 2021, "fuel": "petrol", "transmission": "manual"},
        listing_kwargs={"source_listing_id": "L2", "country": "FR"},
        snapshot_kwargs={"price": 30000, "mileage": 20000},
    )

    cases = [
        {"brand": "BMW"},
        {"price_max": 20000},
        {"price_min": 20000},
        {"mileage_max": 50000},
        {"year_min": 2020},
        {"fuel": "petrol"},
        {"transmission": "automatic"},
        {"country": "DE"},
    ]
    for params in cases:
        assert client.get("/api/v1/listings", params=params).json()["total"] == 1, params

    assert client.get("/api/v1/listings", params={"brand": "Nada"}).json()["total"] == 0
    assert client.get("/api/v1/listings", params={"model": "4"}).json()["total"] == 1


def test_listings_pagination(committed_session) -> None:
    for i in range(25):
        _seed_one(
            committed_session,
            vehicle_kwargs={"brand": "BMW", "model": f"M{i}", "year": 2015 + i % 8},
            listing_kwargs={"source_listing_id": f"P{i}"},
            snapshot_kwargs={"price": 10000 + i},
        )

    page1 = client.get("/api/v1/listings", params={"page": 1, "page_size": 10}).json()
    assert page1["total"] == 25
    assert page1["pages"] == 3
    assert len(page1["items"]) == 10

    page2 = client.get("/api/v1/listings", params={"page": 2, "page_size": 10}).json()
    assert len(page2["items"]) == 10
    ids_1 = {i["id"] for i in page1["items"]}
    ids_2 = {i["id"] for i in page2["items"]}
    assert ids_1.isdisjoint(ids_2)


def test_listing_detail(committed_session) -> None:
    _, l = _seed_one(committed_session, snapshot_kwargs={"price": 15900, "mileage": 80000})

    now = datetime.now(timezone.utc)
    committed_session.add(
        ListingSnapshot(
            listing_id=l.id,
            scraped_at=now - timedelta(days=1),
            price=Decimal(17000),
            mileage=79000,
        )
    )
    committed_session.add(
        ListingEvent(
            listing_id=l.id,
            event_type=ListingEventType.PRICE_CHANGED,
            event_timestamp=now,
            old_value={"price": "17000"},
            new_value={"price": "15900"},
        )
    )
    committed_session.commit()

    response = client.get(f"/api/v1/listings/{l.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "BMW"
    assert body["price"] == 15900.0
    assert body["current_snapshot"]["price"] == 15900.0
    assert body["current_snapshot"]["mileage"] == 80000
    assert body["vehicle"]["brand"] == "BMW"
    assert len(body["snapshots"]) == 2
    assert body["snapshots"][0]["price"] == 17000.0
    assert body["snapshots"][1]["price"] == 15900.0
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == "PRICE_CHANGED"
    assert body["photo_analyses"] == []


def test_listing_detail_404(committed_session) -> None:
    assert client.get("/api/v1/listings/999999").status_code == 404
