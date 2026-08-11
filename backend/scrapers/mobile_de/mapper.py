"""Mapper de registros raw de mobile.de a `NormalizedListing`.

Los anuncios del SRP real llegan como strings "display" en alemán dentro de
`attr` (ej. `pw: "162 kW (220 PS)"`, `ml: "102.696 km"`, `fr: "10/2013"`).
Este mapper los normaliza con vocabulario canónico neutro:

- fuel: petrol | diesel | electric | hybrid | plug-in-hybrid | lpg | cng | hydrogen
- transmission: manual | automatic | semi-automatic | dual-clutch | cvt
- seller_type: commercial | dealer | private

Valores desconocidos o ausentes → `None` (nunca se inventan señales).
"""

import re
from datetime import datetime, timezone

from scrapers.base.interfaces import BaseMapper
from scrapers.base.models import NormalizedListing

_FUEL_MAP = {
    "benzin": "petrol",
    "diesel": "diesel",
    "elektro": "electric",
    "elektrisch": "electric",
    "e-auto": "electric",
    "hybrid": "hybrid",
    "plug-in-hybrid": "plug-in-hybrid",
    "erdgas": "cng",
    "cng": "cng",
    "autogas": "lpg",
    "lpg": "lpg",
    "wasserstoff": "hydrogen",
}

_TRANSMISSION_MAP = {
    "schaltgetriebe": "manual",
    "manuell": "manual",
    "automatik": "automatic",
    "automatikgetriebe": "automatic",
    "halbautomatik": "semi-automatic",
    "tiptronic": "semi-automatic",
    "doppelkupplung": "dual-clutch",
    "doppelkupplungsgetriebe": "dual-clutch",
    "dsg": "dual-clutch",
    "cvt": "cvt",
}

_BASE_HOST = "https://suchen.mobile.de"


def _lookup(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return None
    return mapping.get(value.lower().strip())


def _parse_german_int(text: str | None) -> int | None:
    """'102.696 km' → 102696; '1.984 cm³' → 1984."""
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text.replace(",", "."))
    if not match:
        return None
    digits = match.group(0).replace(".", "")
    if not digits.isdigit():
        return None
    return int(digits)


def _parse_power_kw(text: str | None) -> float | None:
    """'162 kW (220 PS)' → 162.0."""
    if not text:
        return None
    match = re.search(r"([\d]+[\d.,]?)\s*kW", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_year(text: str | None) -> int | None:
    """'10/2013' → 2013 (tolera formatos MM/YYYY o ISO YYYY-MM)."""
    if not text:
        return None
    match = re.search(r"\b(?:19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def _parse_seller_type(contact_info: dict) -> str | None:
    label = (contact_info or {}).get("typeLocalized")
    if not label:
        return None
    lower = label.lower()
    if "privat" in lower:
        return "private"
    if "händler" in lower or "handler" in lower:
        return "dealer"
    if "gewerblich" in lower or "commercial" in lower:
        return "commercial"
    return None


def _get_price(item: dict) -> float:
    price = item.get("price")
    if not isinstance(price, dict):
        raise TypeError("precio no es un objeto")
    amount = price.get("grossAmount")
    if amount is None:
        amount = price.get("netAmount")
    if amount is None:
        raise ValueError("anuncio sin precio")
    return float(amount)


def _get_url(item: dict) -> str:
    relative = item.get("relativeUrl")
    if relative:
        return f"{_BASE_HOST}{relative}"
    return f"{_BASE_HOST}/fahrzeuge/details.html?id={item.get('id')}"


def _get_image_urls(item: dict) -> list[str]:
    urls: list[str] = []
    for thumb in item.get("previewThumbnails") or []:
        src = thumb.get("src") if isinstance(thumb, dict) else thumb
        if src and src not in urls:
            urls.append(src)
    preview = item.get("previewImage")
    src = preview.get("src") if isinstance(preview, dict) else None
    if src and src not in urls:
        urls.append(src)
    return urls


class MobileDeMapper(BaseMapper):
    """Convierte un anuncio raw del SRP en un `NormalizedListing`."""

    def map(self, record: dict) -> NormalizedListing:
        source_id = record.get("id")
        if source_id is None:
            raise ValueError("anuncio sin id")
        brand = record.get("make")
        model = record.get("model")
        if not brand or not model:
            raise ValueError("anuncio sin marca/modelo")

        attr = record.get("attr")
        if not isinstance(attr, dict):
            raise TypeError("anuncio sin attr")
        country = attr.get("cn")
        if not country:
            raise ValueError("anuncio sin país")

        contact_info = record.get("contactInfo") or {}

        return NormalizedListing(
            source="mobile_de",
            source_listing_id=str(source_id),
            url=_get_url(record),
            brand=brand,
            model=model,
            year=_parse_year(attr.get("fr")),
            mileage=_parse_german_int(attr.get("ml")),
            fuel=_lookup(attr.get("ft"), _FUEL_MAP),
            transmission=_lookup(attr.get("tr"), _TRANSMISSION_MAP),
            power_kw=_parse_power_kw(attr.get("pw")),
            co2_g_km=_parse_german_int(attr.get("emiss")),
            price=_get_price(record),
            currency=(record.get("price") or {}).get("grossCurrency", "EUR"),
            seller_type=_parse_seller_type(contact_info),
            country=country,
            city=attr.get("loc"),
            title=record.get("title") or f"{brand} {model}",
            description=None,
            image_urls=_get_image_urls(record),
            scraped_at=datetime.now(timezone.utc),
        )
