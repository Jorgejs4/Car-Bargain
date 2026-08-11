"""Contrato común producido por todos los scrapers."""

from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedListing(BaseModel):
    """Anuncio normalizado, independiente de la fuente.

    Toda fuente produce este objeto; si una fuente cambia, solo se adapta su scraper.
    """

    source: str
    source_listing_id: str
    url: str

    brand: str
    model: str
    generation: str | None = None
    variant: str | None = None

    year: int | None = None
    mileage: int | None = None

    fuel: str | None = None
    transmission: str | None = None
    power_kw: float | None = None
    co2_g_km: float | None = None

    price: float
    currency: str = "EUR"

    seller_type: str | None = None

    country: str
    city: str | None = None

    title: str
    description: str | None = None

    image_urls: list[str] = Field(default_factory=list)

    scraped_at: datetime
