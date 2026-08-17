import json
from datetime import timezone
from pathlib import Path

import httpx
import pytest
from scrapers.mobile_de.wayback import MobileDeHistoricalScraper, WaybackError

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mobile_de" / "search_page.html"

CDX_HEADER = ["timestamp", "original", "statuscode", "mimetype"]
SNAPSHOT_TS = "20251205031456"


def _cdx_rows(*rows: list) -> list:
    return [CDX_HEADER, *rows]


def _state_html_with_wayback_images() -> str:
    item = {
        "id": 1,
        "make": "Audi",
        "model": "A4",
        "price": {"grossAmount": 10000, "grossCurrency": "EUR"},
        "relativeUrl": "/fahrzeuge/details.html?id=1&vc=Car",
        "contactInfo": {"typeLocalized": "Privat"},
        "attr": {"cn": "DE", "loc": "Berlin", "ml": "50.000 km", "ft": "Benzin", "tr": "Schaltgetriebe", "pw": "100 kW"},
        "previewThumbnails": [{"src": f"https://web.archive.org/web/{SNAPSHOT_TS}id_/https://img/a.jpg"}],
    }
    state = {"search": {"srp": {"data": {"searchResults": {"items": [item]}}, "status": "loaded"}}}
    return f"<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script>"


def _scraper_with(handler) -> MobileDeHistoricalScraper:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return MobileDeHistoricalScraper(client=client)


def _handler(fixture_html: str, cdx_rows: list | None) -> callable:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/cdx"):
            return httpx.Response(200, json=cdx_rows or _cdx_rows())
        return httpx.Response(200, text=fixture_html)

    return handler


def test_list_snapshots_returns_rows_sorted_recent_first() -> None:
    rows = _cdx_rows(
        ["20251205031456", "https://suchen.mobile.de/fahrzeuge/search.html", "200", "text/html"],
        ["20250208070709", "https://suchen.mobile.de/fahrzeuge/search.html", "200", "text/html"],
    )
    scraper = _scraper_with(_handler("", rows))
    snapshots = scraper.list_snapshots("https://suchen.mobile.de/fahrzeuge/search.html")
    assert [s["timestamp"] for s in snapshots] == ["20251205031456", "20250208070709"]
    assert snapshots[0]["statuscode"] == "200"


def test_list_snapshots_empty_when_no_rows() -> None:
    scraper = _scraper_with(_handler("", _cdx_rows()))
    assert scraper.list_snapshots("https://suchen.mobile.de/fahrzeuge/search.html") == []


def test_run_latest_maps_real_fixture() -> None:
    fixture = FIXTURE.read_text(encoding="utf-8")
    rows = _cdx_rows([SNAPSHOT_TS, "https://suchen.mobile.de/fahrzeuge/search.html", "200", "text/html"])
    scraper = _scraper_with(_handler(fixture, rows))
    listings = scraper.run_latest("https://suchen.mobile.de/fahrzeuge/search.html")
    assert len(listings) == 24
    assert listings[0].scraped_at.year == 2025
    assert listings[0].scraped_at.tzinfo == timezone.utc


def test_run_with_timestamp_sets_scraped_at() -> None:
    scraper = _scraper_with(_handler(_state_html_with_wayback_images(), None))
    listings = scraper.run("https://suchen.mobile.de/fahrzeuge/search.html", SNAPSHOT_TS)
    assert len(listings) == 1
    assert listings[0].scraped_at.strftime("%Y%m%d%H%M%S") == SNAPSHOT_TS


def test_run_cleans_wayback_image_prefixes() -> None:
    scraper = _scraper_with(_handler(_state_html_with_wayback_images(), None))
    listings = scraper.run("https://suchen.mobile.de/fahrzeuge/search.html", SNAPSHOT_TS)
    assert listings[0].image_urls == ["https://img/a.jpg"]


def test_run_latest_raises_when_no_snapshots() -> None:
    scraper = _scraper_with(_handler("", _cdx_rows()))
    with pytest.raises(WaybackError, match="No hay snapshots"):
        scraper.run_latest("https://suchen.mobile.de/fahrzeuge/search.html")


def test_fetch_snapshot_raises_on_access_denied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<title>Zugriff verweigert / Access denied</title>")

    scraper = _scraper_with(handler)
    with pytest.raises(WaybackError, match="acceso denegado"):
        scraper.run("https://suchen.mobile.de/fahrzeuge/search.html", SNAPSHOT_TS)
