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
    monkeypatch.setattr(tasks, "_enqueue_analyze", lambda *a, **k: None)

    def handler(request: httpx.Request) -> httpx.Response:
        content_type = "image/png" if request.url.path.endswith(".png") else "image/jpeg"
        return httpx.Response(200, content=b"\x00\x01fake-image", headers={"content-type": content_type})

    monkeypatch.setattr(
        "app.services.listing_images._image_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

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


def test_download_listing_images_enqueues_analyze(monkeypatch, tmp_path) -> None:
    from workers import tasks

    listing_id = _make_committed_listing({"image_urls": ["https://pictures.mobile.de/1"]})
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)
    enqueued: list[int] = []
    monkeypatch.setattr(tasks, "_enqueue_analyze", lambda lid: enqueued.append(lid))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

    monkeypatch.setattr(
        "app.services.listing_images._image_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    tasks.download_listing_images(listing_id)

    assert enqueued == [listing_id]


def test_download_listing_images_reports_failures(monkeypatch, tmp_path) -> None:
    from workers import tasks

    listing_id = _make_committed_listing(
        {"image_urls": ["https://pictures.mobile.de/1", "https://pictures.mobile.de/2"]}
    )
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(tasks, "_enqueue_analyze", lambda *a, **k: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403 if request.url.path.endswith("/2") else 200, content=b"data")

    monkeypatch.setattr(
        "app.services.listing_images._image_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

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


class _FakeAnalyzer:
    model_version = "fake/1.0"

    def __init__(self, results: list[tuple[str, float]]) -> None:
        self._results = results
        self._index = 0

    def classify(self, image_path: str):
        from app.schemas.photo_analysis import PhotoAnalysisResult

        label, probability = self._results[self._index % len(self._results)]
        self._index += 1
        return PhotoAnalysisResult(label=label, probability=probability, model_version=self.model_version)


def _make_committed_listing_with_images(tmp_path, urls: list[str]) -> int:
    """Crea listing + snapshot con imágenes locales + manifest en tmp_path."""
    import json as _json

    listing_id = _make_committed_listing({"image_urls": urls})
    image_dir = tmp_path / "mobile_de" / "images" / "IMG-001"
    image_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for index, url in enumerate(urls, start=1):
        image_file = image_dir / f"{index:02d}.jpg"
        image_file.write_bytes(b"fake-image-bytes")
        paths[url] = str(image_file)
    (image_dir / "manifest.json").write_text(
        _json.dumps(
            {
                "images": [
                    {"source_url": url, "local_path": path, "status": "ok"} for url, path in paths.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    return listing_id


def test_analyze_listing_images_task(monkeypatch, tmp_path) -> None:
    from workers import tasks

    urls = ["https://pictures.mobile.de/1", "https://pictures.mobile.de/2"]
    listing_id = _make_committed_listing_with_images(tmp_path, urls)
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(
        tasks,
        "get_vision_analyzer",
        lambda: _FakeAnalyzer([("sin daños", 0.9), ("abolladura", 0.8)]),
    )

    result = tasks.analyze_listing_images(listing_id)

    assert result["status"] == "done"
    assert result["analyzed"] == 2
    assert result["failed"] == 0
    assert result["has_visible_damage"] is True
    assert result["needs_review"] is False

    from app.db.session import engine
    from app.models import Listing, PhotoAnalysis

    with Session(engine) as db:
        analyses = db.scalars(select(PhotoAnalysis).where(PhotoAnalysis.listing_id == listing_id)).all()
        assert len(analyses) == 2
        labels = {a.label for a in analyses}
        assert labels == {"sin daños", "abolladura"}

        listing = db.get(Listing, listing_id)
        assert listing.photo_signals["has_visible_damage"] is True
        assert listing.photo_signals["damage_types"] == ["abolladura"]
        assert listing.photo_signals["photo_damage_prob"] == 0.8
        assert listing.needs_review is False
        assert listing.risk_score is not None


def test_analyze_listing_images_text_photo_contradiction(monkeypatch, tmp_path) -> None:
    from datetime import datetime, timezone

    from app.db.session import engine
    from app.models import Listing, ListingSnapshot
    from workers import tasks

    listing_id = _make_committed_listing({"image_urls": ["https://pictures.mobile.de/1"]})
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)
    with Session(engine) as db:
        listing = db.get(Listing, listing_id)
        listing.photo_signals = None
        listing.needs_review = False
        listing.risk_score = None
        db.add(
            ListingSnapshot(
                listing_id=listing_id,
                scraped_at=datetime.now(timezone.utc),
                price=10000.0,
                condition_signals={
                    "accident_free": True,
                    "has_accident": False,
                    "has_cosmetic_damage": False,
                    "has_rust": False,
                    "has_engine_issue": False,
                    "text_contradiction": False,
                },
                raw_data={"image_urls": ["https://pictures.mobile.de/1"]},
            )
        )
        db.commit()

    image_dir = tmp_path / "mobile_de" / "images" / "IMG-001"
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / "01.jpg").write_bytes(b"data")
    import json as _json

    (image_dir / "manifest.json").write_text(
        _json.dumps(
            {
                "images": [
                    {
                        "source_url": "https://pictures.mobile.de/1",
                        "local_path": str(image_dir / "01.jpg"),
                        "status": "ok",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        tasks, "get_vision_analyzer", lambda: _FakeAnalyzer([("óxido", 0.9)])
    )

    result = tasks.analyze_listing_images(listing_id)

    assert result["needs_review"] is True
    assert result["risk_score"] == 1.0

    with Session(engine) as db:
        listing = db.get(Listing, listing_id)
        assert listing.needs_review is True
        assert listing.photo_signals["has_visible_damage"] is True


def test_analyze_listing_images_cv_unavailable(monkeypatch, tmp_path) -> None:
    from workers import tasks

    listing_id = _make_committed_listing({"image_urls": ["https://pictures.mobile.de/1"]})
    monkeypatch.setattr("app.services.raw_store._DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(
        tasks,
        "get_vision_analyzer",
        lambda: (_ for _ in ()).throw(tasks.VisionUnavailableError("no torch")),
    )

    result = tasks.analyze_listing_images(listing_id)

    assert result["status"] == "cv_unavailable"


def test_analyze_pending_listings_enqueues_only_unanalyzed(monkeypatch, tmp_path) -> None:
    from datetime import datetime, timezone

    from app.db.session import engine
    from app.models import Listing, ListingStatus, PhotoAnalysis
    from workers import tasks

    def _listing(sid: str) -> int:
        with Session(engine) as db:
            listing = Listing(
                source="mobile_de",
                source_listing_id=sid,
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
                    raw_data={"image_urls": ["https://pictures.mobile.de/1"]},
                )
            )
            db.commit()
            return listing.id

    id_a = _listing("P-1")
    id_b = _listing("P-2")
    analyzed_id = _listing("P-3")

    with Session(engine) as db:
        db.add(
            PhotoAnalysis(
                listing_id=analyzed_id,
                image_url="https://pictures.mobile.de/1",
                label="sin daños",
                probability=0.9,
                analyzed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    monkeypatch.setattr(tasks, "get_vision_analyzer", lambda: object())
    enqueued: list[int] = []
    monkeypatch.setattr(tasks, "_enqueue_analyze", lambda lid: enqueued.append(lid))

    result = tasks.analyze_pending_listings(limit=50)

    assert result["enqueued"] == 2
    assert sorted(enqueued) == sorted([id_a, id_b])
    assert analyzed_id not in enqueued
