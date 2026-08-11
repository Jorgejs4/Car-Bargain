import json
from pathlib import Path

import httpx
import pytest
from scrapers.autoscout24.mapper import AutoScout24Mapper
from scrapers.autoscout24.parser import AutoScout24Parser, ParseError
from scrapers.autoscout24.scraper import AutoScout24Scraper

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "autoscout24" / "srp.json"


@pytest.fixture()
def fixture_state() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def parser() -> AutoScout24Parser:
    return AutoScout24Parser()


@pytest.fixture()
def mapper() -> AutoScout24Mapper:
    return AutoScout24Mapper()


def _srp_html(state: dict) -> str:
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'


def _listing_record(**overrides) -> dict:
    record = {
        "id": "17c65c53-eb28-4cf9-89c0-1f8c69c74567",
        "url": "/anuncios/citroen-c4-cactus-bluehdi-100-feel-diesel-blanco-cat_ma21mo20406-17c65c53-eb28-4cf9-89c0-1f8c69c74567",
        "images": ["https://img.as24/a.jpg", "https://img.as24/b.jpg"],
        "price": {"priceRaw": 3890, "priceFormatted": "€ 3.890"},
        "vehicle": {
            "make": "Citroen",
            "model": "C4 Cactus",
            "modelGroup": "C4 Cactus",
            "modelVersionInput": "BlueHDi 100 Feel",
            "transmission": "manual",
            "fuel": "Diésel",
            "mileageInKm": "220.957 km",
        },
        "location": {"countryCode": "ES", "zip": "28914", "city": "Leganés"},
        "seller": {"type": "Dealer", "companyName": "CARHAY LEGANES"},
        "vehicleDetails": [
            {"data": "220.957 km", "iconName": "mileage_odometer", "ariaLabel": "Kilometraje"},
            {"data": "manual", "iconName": "gearbox", "ariaLabel": "Transmisión"},
            {"data": "10/2015", "iconName": "calendar", "ariaLabel": "Año"},
            {"data": "Diésel", "iconName": "gas_pump", "ariaLabel": "Tipo de combustible"},
            {"data": "73 kW (99 CV)", "iconName": "speedometer", "ariaLabel": "Potencia"},
        ],
    }
    record.update(overrides)
    return record


# --- Parser ---


def test_parser_extracts_listings_from_real_fixture(parser) -> None:
    records = parser.parse(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert len(records) == 2
    first = records[0]
    assert first["id"] == "17c65c53-eb28-4cf9-89c0-1f8c69c74567"
    assert first["vehicle"]["make"] == "Citroen"
    assert first["price"]["priceRaw"] == 3890


def test_parser_extracts_from_html(parser, fixture_state) -> None:
    records = parser.parse(_srp_html(fixture_state))
    assert len(records) == 2


def test_parser_accepts_state_without_listings(parser) -> None:
    assert parser.parse({"props": {"pageProps": {}}}) == []
    assert parser.parse("{}") == []
    assert parser.parse({"props": {}}) == []


def test_parser_raises_on_unrecognized_html(parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("<html><body>Hola</body></html>")


# --- Mapper ---


def test_mapper_maps_used_car(mapper) -> None:
    listing = mapper.map(_listing_record())
    assert listing.source == "autoscout24"
    assert listing.source_listing_id == "17c65c53-eb28-4cf9-89c0-1f8c69c74567"
    assert listing.brand == "Citroen"
    assert listing.model == "C4 Cactus"
    assert listing.variant == "BlueHDi 100 Feel"
    assert listing.year == 2015
    assert listing.mileage == 220957
    assert listing.power_kw == 73.0
    assert listing.fuel == "diesel"
    assert listing.transmission == "manual"
    assert listing.price == 3890
    assert listing.currency == "EUR"
    assert listing.seller_type == "dealer"
    assert listing.country == "ES"
    assert listing.city == "Leganés"
    assert listing.title == "Citroen C4 Cactus BlueHDi 100 Feel"
    assert listing.image_urls == ["https://img.as24/a.jpg", "https://img.as24/b.jpg"]


def test_mapper_cv_only_power(mapper) -> None:
    details = [{"data": "99 CV", "iconName": "speedometer", "ariaLabel": "Potencia"}]
    listing = mapper.map(_listing_record(vehicleDetails=details))
    assert listing.power_kw == pytest.approx(72.8, abs=0.1)


def test_mapper_private_seller(mapper) -> None:
    listing = mapper.map(_listing_record(seller={"type": "Private"}))
    assert listing.seller_type == "private"


def test_mapper_unknown_values_to_none(mapper) -> None:
    listing = mapper.map(
        _listing_record(
            vehicle={
                "make": "Citroen",
                "model": "C4 Cactus",
                "transmission": "Warp",
                "fuel": "Gravedad",
                "mileageInKm": "N/D",
            },
            vehicleDetails=[],
        )
    )
    assert listing.fuel is None
    assert listing.transmission is None
    assert listing.year is None
    assert listing.mileage is None


@pytest.mark.parametrize(
    "broken",
    [
        _listing_record(price={"priceFormatted": "€ 3.890"}),
        _listing_record(id=None),
        _listing_record(vehicle=None),
        _listing_record(vehicle={"make": "BMW"}),
        _listing_record(location={"zip": "28914"}),
    ],
    ids=["sin-precio", "sin-id", "sin-vehicle", "sin-modelo", "sin-pais"],
)
def test_mapper_rejects_invalid_records(mapper, broken) -> None:
    with pytest.raises((ValueError, TypeError)):
        mapper.map(broken)


# --- Scraper ---


def test_scraper_full_pipeline(fixture_state) -> None:
    html = _srp_html(fixture_state)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = AutoScout24Scraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    listings = scraper.run(max_pages=1)

    assert len(listings) == 2
    first = next(l for l in listings if l.source_listing_id.startswith("17c65c53"))
    assert first.brand == "Citroen"
    assert first.price == 3890
    assert first.country == "ES"


def test_scraper_propagates_403() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    scraper = AutoScout24Scraper(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="403"):
        scraper.run()


def test_scraper_page_marker_in_build_url() -> None:
    assert "page=2" in AutoScout24Scraper._build_url(2)