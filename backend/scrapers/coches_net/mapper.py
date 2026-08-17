"""Mapper de registros raw de coches.net a `NormalizedListing`.

Los anuncios del SRP llegan desde `initialResults.items` con campos en español
(localizados). Este mapper traduce al vocabulario canónico neutro del proyecto.

Campos reales verificados en vivo (2026-08, fixture `srp.json`):
- `id`, `url` (relativa `.aspx`), `photos`, `price`, `km`, `year`, `hp` (CV),
- `make`, `model`, `title`, `fuelType` ("Diésel", "Gasolina", "Híbrido"...),
- `location.mainProvince/cityLiteral/regionLiteral`,
- `isProfessional` (concesionario vs particular).

coches.net no expone transmisión en el SRP → `transmission=None` (unknown);
`hp` se convierte a kW (1 CV = 0.7355 kW).
"""

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
    "gnc": "cng",
    "hidrógeno": "hydrogen",
    "hidrogeno": "hydrogen",
}

_BASE_HOST = "https://www.coches.net"

_KW_PER_CV = 0.7355


def _lookup(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return None
    return mapping.get(value.lower().strip())


def _cv_to_kw(hp: int | None) -> float | None:
    if hp is None:
        return None
    return round(hp * _KW_PER_CV, 1)


class CochesNetMapper(BaseMapper):
    """Convierte un anuncio raw del SRP en un `NormalizedListing`."""

    def map(self, record: dict) -> NormalizedListing:
        source_id = record.get("id")
        if not source_id:
            raise ValueError("anuncio sin id")

        brand = record.get("make")
        model = record.get("model")
        if not brand or not model:
            raise ValueError("anuncio sin marca/modelo")

        price = record.get("price")
        if price is None:
            raise ValueError("anuncio sin precio")

        location = record.get("location") or {}
        city = location.get("cityLiteral") or location.get("mainProvince")

        title = record.get("title") or f"{brand} {model}"
        photos = [url for url in (record.get("photos") or []) if url]

        seller_type = "dealer" if record.get("isProfessional") is True else "private"

        return NormalizedListing(
            source="coches_net",
            source_listing_id=str(source_id),
            url=f"{_BASE_HOST}{record['url']}" if record.get("url") else f"{_BASE_HOST}/segunda-mano/",
            brand=brand,
            model=model,
            generation=None,
            variant=None,
            year=record.get("year") or None,
            mileage=record.get("km") or None,
            fuel=_lookup(record.get("fuelType"), _FUEL_MAP),
            transmission=None,  # no expuesta en el SRP
            power_kw=_cv_to_kw(record.get("hp")),
            co2_g_km=None,
            price=float(price),
            currency="EUR",
            seller_type=seller_type,
            country="ES",
            city=city,
            title=title,
            description=extract_record_description(record),
            image_urls=photos,
            scraped_at=datetime.now(timezone.utc),
        )
