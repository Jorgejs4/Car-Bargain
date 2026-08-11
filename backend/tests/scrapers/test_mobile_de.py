import json
from pathlib import Path

import httpx
import pytest
from scrapers.mobile_de.mapper import MobileDeMapper
from scrapers.mobile_de.parser import MobileDeParser, ParseError
from scrapers.mobile_de.scraper import MobileDeScraper

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mobile_de" / "search_page.html"


@pytest.fixture()
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture()
def parser() -> MobileDeParser:
    return MobileDeParser()


@pytest.fixture()
def mapper() -> MobileDeMapper:
    return MobileDeMapper()


def _used_car_record(**overrides) -> dict:
    record = {
        "id": 422503915,
        "make": "Volkswagen",
        "model": "Golf",
        "title": "Volkswagen Golf GTI",
        "price": {"grossAmount": 14990, "grossCurrency": "EUR"},
        "relativeUrl": "/fahrzeuge/details.html?id=422503915&vc=Car",
        "contactInfo": {"typeLocalized": "Händler", "name": "Autohaus Test"},
        "attr": {
            "cn": "DE",
            "loc": "Gebesee",
            "fr": "10/2013",
            "pw": "162 kW (220 PS)",
            "ft": "Benzin",
            "ml": "102.696 km",
            "cc": "1.984 cm³",
            "tr": "Schaltgetriebe",
            "emiss": "116 g CO₂/km (komb.)",
        },
        "previewThumbnails": [{"src": "https://img/a.jpg"}, {"src": "https://img/b.jpg"}],
        "previewImage": {"src": "https://img/a.jpg"},
    }
    record.update(overrides)
    return record


# --- Parser ---


def test_parser_extracts_ads_from_real_fixture(parser, fixture_html) -> None:
    records = parser.parse(fixture_html)
    assert len(records) == 24
    assert records[0]["make"] == "Skoda"
    assert records[0]["id"] == 422503914
    assert records[0]["price"]["grossAmount"] == 17690


def test_parser_accepts_state_dict(parser) -> None:
    state = {
        "search": {
            "srp": {
                "data": {"searchResults": {"items": [{"id": 1, "make": "BMW"}]}},
                "status": "loaded",
            }
        }
    }
    records = parser.parse(state)
    assert [r["id"] for r in records] == [1]


def test_parser_returns_empty_for_missing_results(parser) -> None:
    empty_state = {"search": {"srp": {"data": None, "status": "empty"}}}
    assert parser.parse(empty_state) == []
    assert parser.parse({"search": {}}) == []


def test_parser_raises_on_unrecognized_html(parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("<html><body>Hola</body></html>")


# --- Mapper ---


def test_mapper_maps_used_car(mapper) -> None:
    listing = mapper.map(_used_car_record())
    assert listing.source == "mobile_de"
    assert listing.source_listing_id == "422503915"
    assert listing.brand == "Volkswagen"
    assert listing.model == "Golf"
    assert listing.year == 2013
    assert listing.mileage == 102696
    assert listing.power_kw == 162.0
    assert listing.co2_g_km == 116
    assert listing.fuel == "petrol"
    assert listing.transmission == "manual"
    assert listing.price == 14990
    assert listing.currency == "EUR"
    assert listing.seller_type == "dealer"
    assert listing.country == "DE"
    assert listing.city == "Gebesee"
    assert listing.title == "Volkswagen Golf GTI"
    assert listing.url == "https://suchen.mobile.de/fahrzeuge/details.html?id=422503915&vc=Car"
    assert listing.image_urls == ["https://img/a.jpg", "https://img/b.jpg"]


def test_mapper_private_and_unknown_seller(mapper) -> None:
    private = _used_car_record(contactInfo={"typeLocalized": "Privat"})
    assert mapper.map(private).seller_type == "private"

    unknown = _used_car_record(contactInfo={})
    assert mapper.map(unknown).seller_type is None


def test_mapper_net_price_fallback(mapper) -> None:
    record = _used_car_record(price={"grossAmount": None, "netAmount": 12345.67})
    assert mapper.map(record).price == 12345.67


def test_mapper_url_fallback_without_relative_url(mapper) -> None:
    record = _used_car_record(relativeUrl=None)
    assert mapper.map(record).url == "https://suchen.mobile.de/fahrzeuge/details.html?id=422503915"


def test_mapper_returns_none_for_unknown_values(mapper) -> None:
    record = _used_car_record(
        attr={
            "cn": "DE",
            "loc": "München",
            "pw": "n/a",
            "ft": "Schwerkraft",
            "ml": "unbekannt",
            "tr": "Warp",
        }
    )
    listing = mapper.map(record)
    assert listing.year is None
    assert listing.mileage is None
    assert listing.power_kw is None
    assert listing.fuel is None
    assert listing.transmission is None


@pytest.mark.parametrize(
    "broken",
    [
        _used_car_record(price=None),
        _used_car_record(id=None),
        _used_car_record(attr={"loc": "München"}),  # sin país
        _used_car_record(attr=None),
    ],
    ids=["sin-precio", "sin-id", "sin-pais", "sin-attr"],
)
def test_mapper_rejects_invalid_records(mapper, broken) -> None:
    with pytest.raises((ValueError, TypeError)):
        mapper.map(broken)


# --- Scraper ---


def test_scraper_full_pipeline(fixture_html) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture_html)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    listings = scraper.run(max_pages=1)

    assert len(listings) == 24
    first = next(l for l in listings if l.source_listing_id == "422503914")
    assert first.brand == "Skoda"
    assert first.price == 17690
    assert first.country == "DE"


def test_scraper_skips_unmappable_records() -> None:
    state = {
        "search": {
            "srp": {
                "data": {
                    "searchResults": {
                        "items": [
                            _used_car_record(id=1),
                            _used_car_record(id=2, price=None),
                        ]
                    }
                },
                "status": "loaded",
            }
        }
    }
    html = f"<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    listings = scraper.run()
    assert len(listings) == 1
    assert listings[0].source_listing_id == "1"


def test_scraper_propagates_403() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    scraper = MobileDeScraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="403"):
        scraper.run()
