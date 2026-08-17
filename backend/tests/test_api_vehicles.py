"""Tests de la API REST de vehículos (Fase 4)."""

from datetime import datetime, timedelta, timezone

from app.main import app
from app.models import ListingStatus
from fastapi.testclient import TestClient

from tests import helpers

client = TestClient(app)


def _seed_vehicle(committed_session, *, n_active=0, n_removed=0):
    vehicle = helpers.make_vehicle(committed_session)
    for i in range(n_active):
        listing = helpers.make_listing(committed_session, vehicle=vehicle, source_listing_id=f"A{i}")
        helpers.make_snapshot(committed_session, listing, price=10000 + i * 2000)
    for i in range(n_removed):
        listing = helpers.make_listing(
            committed_session, vehicle=vehicle, source_listing_id=f"R{i}", status=ListingStatus.REMOVED
        )
        helpers.make_snapshot(committed_session, listing, price=99999)
    committed_session.commit()
    return vehicle


def test_vehicle_detail(committed_session) -> None:
    vehicle = _seed_vehicle(committed_session, n_active=2, n_removed=1)
    response = client.get(f"/api/v1/vehicles/{vehicle.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "BMW"
    assert body["model"] == "320d"
    assert len(body["listings"]) == 2
    assert {l["source_listing_id"] for l in body["listings"]} == {"A0", "A1"}
    assert all(l["status"] == "ACTIVE" for l in body["listings"])


def test_vehicle_history(committed_session) -> None:
    vehicle = helpers.make_vehicle(committed_session)
    listing = helpers.make_listing(committed_session, vehicle=vehicle, source_listing_id="H1")
    base = datetime.now(timezone.utc)
    helpers.make_snapshot(committed_session, listing, price=10000, mileage=80000, scraped_at=base - timedelta(days=2))
    helpers.make_snapshot(committed_session, listing, price=9500, mileage=80050, scraped_at=base)
    committed_session.commit()

    response = client.get(f"/api/v1/vehicles/{vehicle.id}/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["listing_id"] == listing.id
    assert entry["status"] == "ACTIVE"
    prices = [p["price"] for p in entry["snapshots"]]
    assert prices == [10000.0, 9500.0]
    assert entry["snapshots"][0]["mileage"] == 80000


def test_vehicle_market_percentiles(committed_session) -> None:
    vehicle = helpers.make_vehicle(committed_session)
    for i, price in enumerate([10000, 16000, 12000]):
        listing = helpers.make_listing(committed_session, vehicle=vehicle, source_listing_id=f"M{i}")
        helpers.make_snapshot(committed_session, listing, price=price)
    committed_session.commit()

    response = client.get(f"/api/v1/vehicles/{vehicle.id}/market")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["min_price"] == 10000.0
    assert body["p50"] == 12000.0
    assert body["max_price"] == 16000.0
    assert body["mean_price"] == 12666.67
    assert body["p10"] == 10000.0
    assert body["p90"] == 16000.0
    assert body["currency"] == "EUR"


def test_vehicle_market_empty(committed_session) -> None:
    vehicle = _seed_vehicle(committed_session, n_active=0)
    response = client.get(f"/api/v1/vehicles/{vehicle.id}/market")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["p50"] is None


def test_vehicle_404(committed_session) -> None:
    assert client.get("/api/v1/vehicles/999999").status_code == 404
    assert client.get("/api/v1/vehicles/999999/history").status_code == 404
    assert client.get("/api/v1/vehicles/999999/market").status_code == 404
