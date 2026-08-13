"""Mapper de registros raw de AutoScout24 a `NormalizedListing`.

Los anuncios del SRP llegan desde `props.pageProps.listings` con campos en
español (AutoScout24.es). Este mapper los normaliza al vocabulario canónico
neutro del proyecto (fuel, transmission, seller_type).

Campos reales verificados en vivo (2026-08):
- `id` (UUID), `url` (ruta relativa), `images` (lista), `price.priceRaw`,
- `vehicle.make/model/modelVersionInput/fuel/transmission/mileageInKm`,
- `location.countryCode/city/zip`, `seller.type` ("Dealer"/"Private"),
- `vehicleDetails`: pares `{data, ariaLabel}` con año ("10/2015"),
  kilometraje y potencia ("73 kW (99 CV)").

Valores desconocidos o ausentes → `None` (nunca se inventan señales).
"""

import re
from datetime import datetime, timezone

from scrapers.base.detail import extract_record_description
from scrapers.base.interfaces import BaseMapper
from scrapers.base.models import NormalizedListing

_FUEL_MAP = {
    "gasolina": "petrol",
    "diésel": "diesel",
    "diesel": "diesel",
    "eléctrico": "electric",
    "electrico": "electric",
    "híbrido": "hybrid",
    "hibrido": "hybrid",
    "híbrido enchufable": "plug-in-hybrid",
    "hibrido enchufable": "plug-in-hybrid",
    "glp": "lpg",
    "gpl": "lpg",
    "gnc": "cng",
    "hidrógeno": "hydrogen",
    "hidrogeno": "hydrogen",
}

_TRANSMISSION_MAP = {
    "manual": "manual",
    "automático": "automatic",
    "automatic": "automatic",
    "semi-automático": "semi-automatic",
    "semi-automatico": "semi-automatic",
    "doble embrague": "dual-clutch",
    "cvt": "cvt",
}

_SELLER_MAP = {
    "dealer": "dealer",
    "profesional": "dealer",
    "private": "private",
    "particular": "private",
}

_BASE_HOST = "https://www.autoscout24.es"


def _lookup(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return None
    return mapping.get(value.lower().strip())


def _parse_es_number(text: str | None) -> int | None:
    """'220.957 km' → 220957; '10 km' → 10 (miles separados por punto)."""
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    digits = match.group(0).replace(".", "")
    if not digits.isdigit():
        return None
    return int(digits)


def _parse_power_kw(text: str | None) -> float | None:
    """'73 kW (99 CV)' → 73.0 (si solo hay CV: '99 CV' → 72.8 kW)."""
    if not text:
        return None
    match = re.search(r"([\d]+[\d.,]?)\s*kW", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", "."))
    match_cv = re.search(r"([\d]+[\d.,]?)\s*CV", text, re.IGNORECASE)
    if match_cv:
        return round(float(match_cv.group(1).replace(",", ".")) * 0.7355, 1)
    return None


def _parse_year(text: str | None) -> int | None:
    """'10/2015' → 2015 (tolera formatos MM/YYYY o ISO YYYY-MM)."""
    if not text:
        return None
    match = re.search(r"\b(?:19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def _detail_value(vehicle_details, aria_path: tuple[str, ...]) -> str | None:
    """Busca en `vehicleDetails` el `data` de un ítem por su `ariaLabel`."""
    for item in vehicle_details or []:
        label = (item.get("ariaLabel") or "").lower()
        if any(token in label for token in aria_path):
            return item.get("data")
    return None


class AutoScout24Mapper(BaseMapper):
    """Convierte un anuncio raw del SRP en un `NormalizedListing`."""

    def map(self, record: dict) -> NormalizedListing:
        source_id = record.get("id")
        if not source_id:
            raise ValueError("anuncio sin id")

        vehicle = record.get("vehicle")
        if not isinstance(vehicle, dict):
            raise TypeError("anuncio sin vehicle")
        brand = vehicle.get("make")
        model = vehicle.get("model")
        if not brand or not model:
            raise ValueError("anuncio sin marca/modelo")

        price = record.get("price")
        if not isinstance(price, dict) or price.get("priceRaw") is None:
            raise ValueError("anuncio sin precio")
        amount = float(price["priceRaw"])

        location = record.get("location") or {}
        country = location.get("countryCode")
        if not country:
            raise ValueError("anuncio sin país")

        vehicle_details = record.get("vehicleDetails") or []

        seller = record.get("seller") or {}
        seller_type = _lookup(seller.get("type"), _SELLER_MAP)

        variant = (
            vehicle.get("modelVersionInput")
            or vehicle.get("modelVersionCustom")
            or vehicle.get("variant")
            or None
        )
        title = " ".join(part for part in (brand, model, variant) if part)

        image_urls = []
        for url in record.get("images") or []:
            if url and url not in image_urls:
                image_urls.append(url)

        mileage_in_km = vehicle.get("mileageInKm") or _detail_value(
            vehicle_details, ("kilometraje", "mileage")
        )

        return NormalizedListing(
            source="autoscout24",
            source_listing_id=str(source_id),
            url=f"{_BASE_HOST}{record['url']}" if record.get("url") else f"{_BASE_HOST}/anuncios/{source_id}",
            brand=brand,
            model=model,
            generation=vehicle.get("modelGroup") or None,
            variant=variant,
            year=_parse_year(_detail_value(vehicle_details, ("año", "year"))),
            mileage=_parse_es_number(mileage_in_km),
            fuel=_lookup(vehicle.get("fuel"), _FUEL_MAP),
            transmission=_lookup(vehicle.get("transmission"), _TRANSMISSION_MAP),
            power_kw=_parse_power_kw(_detail_value(vehicle_details, ("potencia", "power"))),
            co2_g_km=None,
            price=amount,
            currency="EUR",
            seller_type=seller_type,
            country=country,
            city=location.get("city") or None,
            title=title,
            description=extract_record_description(record),
            image_urls=image_urls,
            scraped_at=datetime.now(timezone.utc),
        )
