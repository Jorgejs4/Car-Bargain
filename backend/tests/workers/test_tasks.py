from pathlib import Path

import httpx
from app.models import Listing, ListingSnapshot
from app.services.raw_store import save_raw
from scrapers.mobile_de.scraper import MobileDeScraper
from sqlalchemy import select
from sqlalchemy.orm import Session

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mobile_de" / "search_page.html"


def _patch_lock(monkeypatch) -> None:
    from workers import tasks

    monkeypatch.setattr(tasks, "_acquire_lock", lambda: True)


def test_scrape_mobile_de_task_ingests(monkeypatch) -> None:
    from workers import tasks

    _patch_lock(monkeypatch)

    fixture = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(tasks, "MobileDeScraper", lambda **kwargs: scraper)
    monkeypatch.setattr(tasks, "save_raw", lambda *a, **k: None)

    result = tasks.scrape_mobile_de(max_pages=1, enqueue_image_downloads=False)

    assert result["source"] == "mobile_de"
    assert result["listings"] == 24
    assert result["listings_created"] == 24
    assert result["snapshots_appended"] == 24
    assert result["events_emitted"] == 24

    from app.db.session import engine

    with Session(engine) as db:
        assert db.scalar(select(Listing).where(Listing.source == "mobile_de")) is not None
        assert db.scalar(select(ListingSnapshot)) is not None


def test_task_saves_raw_local(monkeypatch, tmp_path) -> None:
    from workers import tasks

    _patch_lock(monkeypatch)

    fixture = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(tasks, "MobileDeScraper", lambda **kwargs: scraper)
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)

    saved: list[str] = []

    def fake_save_raw(content, source, name):
        location = save_raw(content, source, name)
        saved.append(location)
        return location

    monkeypatch.setattr(tasks, "save_raw", fake_save_raw)

    tasks.scrape_mobile_de(max_pages=1, enqueue_image_downloads=False)

    assert len(saved) == 1
    assert saved[0] and "srp_page_1.html" in saved[0]
    assert list(tmp_path.rglob("*.html"))


def test_ingest_runs_twice_is_idempotent_for_listing_count(monkeypatch) -> None:
    from workers import tasks

    _patch_lock(monkeypatch)

    fixture = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(tasks, "MobileDeScraper", lambda **kwargs: scraper)
    monkeypatch.setattr(tasks, "save_raw", lambda *a, **k: None)

    tasks.scrape_mobile_de(max_pages=1, enqueue_image_downloads=False)
    second = tasks.scrape_mobile_de(max_pages=1, enqueue_image_downloads=False)

    assert second["listings_created"] == 0
    assert second["snapshots_appended"] == 24

    from app.db.session import engine

    with Session(engine) as db:
        listings = db.scalars(select(Listing).where(Listing.source == "mobile_de")).all()
        assert len(listings) == 24


def test_scrape_task_skips_when_lock_held(monkeypatch) -> None:
    from workers import tasks

    monkeypatch.setattr(tasks, "_acquire_lock", lambda: False)

    result = tasks.scrape_mobile_de(max_pages=1)

    assert result["skipped"] is True
    assert result["reason"] == "lock"


def _make_committed_listing(raw_data: dict) -> int:
    """Inserta un listing+snapshot con una sesión real commiteada (visible para la task)."""
    from datetime import datetime, timezone

    from app.db.session import engine
    from app.models import Listing, ListingSnapshot, ListingStatus

    with Session(engine) as db:
        listing = Listing(
            source="mobile_de",
            source_listing_id="IMG-001",
            first_seen_at=datetime.now(timezone.utc),
            status=ListingStatus.ACTIVE,
        )
        db.add(listing)
        db.flush()
        db.add(
            ListingSnapshot(
                listing_id=listing.id,
                scraped_at=datetime.now(timezone.utc),
                price=10000.0,
                raw_data=raw_data,
            )
        )
        db.commit()
        return listing.id


def test_download_listing_images_task(monkeypatch, tmp_path) -> None:
    from workers import tasks

    listing_id = _make_committed_listing(
        {
            "image_urls": [
                "https://pictures.mobile.de/1?a=1",
                "https://pictures.mobile.de/2.png",
            ]
        }
    )
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        content_type = "image/png" if request.url.path.endswith(".png") else "image/jpeg"
        return httpx.Response(200, content=b"\x00\x01fake-image", headers={"content-type": content_type})

    monkeypatch.setattr(tasks, "_image_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))

    result = tasks.download_listing_images(listing_id)

    assert result["status"] == "done"
    assert result["downloaded"] == 2
    assert result["failed"] == 0

    image_dir = tmp_path / "mobile_de" / "images" / "IMG-001"
    assert (image_dir / "01.jpg").read_bytes() == b"\x00\x01fake-image"
    assert (image_dir / "02.png").read_bytes() == b"\x00\x01fake-image"
    manifest = image_dir / "manifest.json"
    assert manifest.exists()
    assert len(__import__("json").loads(manifest.read_text(encoding="utf-8"))["images"]) == 2


def test_download_listing_images_reports_failures(monkeypatch, tmp_path) -> None:
    from workers import tasks

    listing_id = _make_committed_listing(
        {"image_urls": ["https://pictures.mobile.de/1", "https://pictures.mobile.de/2"]}
    )
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403 if request.url.path.endswith("/2") else 200, content=b"data")

    monkeypatch.setattr(tasks, "_image_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))

    result = tasks.download_listing_images(listing_id)

    assert result["downloaded"] == 1
    assert result["failed"] == 1


def test_update_listing_status_task() -> None:
    from datetime import datetime, timedelta, timezone

    from app.db.session import engine
    from app.models import Listing, ListingEvent, ListingStatus
    from workers import tasks

    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=60)
    stale = now - timedelta(hours=12)
    fresh = now - timedelta(hours=1)

    with Session(engine) as db:
        for sid, last_seen in (("stale", stale), ("removed", old), ("fresh", fresh)):
            db.add(
                Listing(
                    source="mobile_de",
                    source_listing_id=sid,
                    first_seen_at=now,
                    last_seen_at=last_seen,
                    status=ListingStatus.ACTIVE,
                )
            )
        db.commit()

    result = tasks.update_listing_status(source="mobile_de")

    assert result["checked"] == 3
    assert result["stale"] == 1
    assert result["removed"] == 1

    from sqlalchemy import select

    with Session(engine) as db:
        statuses = {
            row.source_listing_id: row.status
            for row in db.scalars(select(Listing).where(Listing.source == "mobile_de"))
        }
        assert statuses["stale"] == "STALE"
        assert statuses["removed"] == "REMOVED"
        assert statuses["fresh"] == "ACTIVE"

        event_types = set(db.scalars(select(ListingEvent.event_type)))
        assert "REMOVED" in event_types
        assert "STATUS_CHANGED" in event_types
