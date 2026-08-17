import json
from pathlib import Path

import httpx
import pytest
from scrapers.coches_net.mapper import CochesNetMapper
from scrapers.coches_net.parser import CochesNetParser, ParseError
from scrapers.coches_net.scraper import CochesNetScraper

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "coches_net" / "srp.json"
FIXTURE_BLOCKED = Path(__file__).resolve().parents[1] / "fixtures" / "coches_net" / "blocked.html"


@pytest.fixture()
def fixture_state() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def parser() -> CochesNetParser:
    return CochesNetParser()


@pytest.fixture()
def mapper() -> CochesNetMapper:
    return CochesNetMapper()


def _srp_html_from_state(state: dict) -> str:
    """Reconstruye el HTML real: `window.__INITIAL_PROPS__ = JSON.parse("...")`."""
    js_string = json.dumps(state).replace('"', '\\"')
    return f'<script>window.__INITIAL_PROPS__ = JSON.parse("{js_string}")</script>'


def _listing_record(**overrides) -> dict:
    record = {
        "id": "71090895",
        "make": "DS",
        "model": "DS 7 Crossback",
        "title": "DS DS 7 Crossback 1.6 E-Tense 300 Louvre auto 4WD 5p eléctrico híbrido 2021",
        "price": 24995,
        "km": 61178,
        "year": 2021,
        "hp": 300,
        "fuelType": "Híbrido enchufable",
        "url": "/ds-ds-7-crossback-16-etense-300-louvre-auto-4wd-5p-electrico-hibrido-2021-en-barcelona-71090895-covo.aspx",
        "isProfessional": True,
        "location": {
            "mainProvince": "Barcelona",
            "cityLiteral": "Barcelona Capital",
            "regionLiteral": "Catalunya",
        },
        "photos": [
            "https://a.ccdn.es/cnet/vehicles/20437878/2fed1f69-2f94-4740-a2de-4f3884a37939.jpg",
            "https://a.ccdn.es/cnet/vehicles/20437878/4f7963e2-73bd-4daf-972b-18f1cffd546d.jpg",
        ],
    }
    record.update(overrides)
    return record


# --- Parser ---


def test_parser_extracts_from_real_fixture(parser, fixture_state) -> None:
    records = parser.parse(fixture_state)
    assert len(records) == 2
    assert records[0]["id"] == "71090895"
    assert records[0]["make"] == "DS"
    assert records[0]["price"] == 24995


def test_parser_extracts_from_html(parser, fixture_state) -> None:
    records = parser.parse(_srp_html_from_state(fixture_state))
    assert len(records) == 2


def test_parser_accepts_empty_results(parser) -> None:
    assert parser.parse({"initialResults": {}}) == []
    assert parser.parse({}) == []


def test_parser_raises_on_blocked_page(parser) -> None:
    blocked = FIXTURE_BLOCKED.read_text(encoding="utf-8")
    with pytest.raises(ParseError, match="INITIAL_PROPS"):
        parser.parse(blocked)


def test_parser_raises_on_unrecognized_html(parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("<html><body>Hola</body></html>")


# --- Mapper ---


def test_mapper_maps_used_car(mapper) -> None:
    listing = mapper.map(_listing_record())
    assert listing.source == "coches_net"
    assert listing.source_listing_id == "71090895"
    assert listing.brand == "DS"
    assert listing.model == "DS 7 Crossback"
    assert listing.year == 2021
    assert listing.mileage == 61178
    assert listing.power_kw == pytest.approx(220.7, abs=0.1)
    assert listing.fuel == "plug-in-hybrid"
    assert listing.transmission is None
    assert listing.price == 24995
    assert listing.seller_type == "dealer"
    assert listing.country == "ES"
    assert listing.city == "Barcelona Capital"
    assert listing.title.startswith("DS DS 7 Crossback")
    assert len(listing.image_urls) == 2


def test_mapper_private_seller(mapper) -> None:
    listing = mapper.map(_listing_record(isProfessional=False))
    assert listing.seller_type == "private"


def test_mapper_gasoline_fuel(mapper) -> None:
    listing = mapper.map(_listing_record(fuelType="Gasolina", hp=90))
    assert listing.fuel == "petrol"
    assert listing.power_kw == pytest.approx(66.2, abs=0.1)


def test_mapper_unknown_values_to_none(mapper) -> None:
    listing = mapper.map(
        _listing_record(fuelType="Antimateria", year=None, km=None, hp=None)
    )
    assert listing.fuel is None
    assert listing.year is None
    assert listing.mileage is None
    assert listing.power_kw is None


@pytest.mark.parametrize(
    "broken",
    [
        _listing_record(price=None),
        _listing_record(id=None),
        _listing_record(make=None),
        _listing_record(model=None),
    ],
    ids=["sin-precio", "sin-id", "sin-marca", "sin-modelo"],
)
def test_mapper_rejects_invalid_records(mapper, broken) -> None:
    with pytest.raises((ValueError, TypeError)):
        mapper.map(broken)


# --- Scraper ---


def test_scraper_full_pipeline(fixture_state) -> None:
    html = _srp_html_from_state(fixture_state)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = CochesNetScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    listings = scraper.run(max_pages=1)

    assert len(listings) == 2
    first = next(l for l in listings if l.source_listing_id == "71090895")
    assert first.brand == "DS"
    assert first.price == 24995
    assert first.country == "ES"


def test_scraper_raises_on_blocked_page() -> None:
    blocked = FIXTURE_BLOCKED.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=blocked)

    scraper = CochesNetScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="anti-bot"):
        scraper.run()


def test_scraper_propagates_403() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    scraper = CochesNetScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="403"):
        scraper.run()


def test_scraper_build_url_pagination() -> None:
    assert CochesNetScraper._build_url(1) == "https://www.coches.net/segunda-mano/"
    assert "pg=3" in CochesNetScraper._build_url(3)