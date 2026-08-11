from datetime import datetime

from pydantic import BaseModel

from app.schemas.listing import ListingListItem
from app.schemas.vehicle import VehicleRead


class PricePoint(BaseModel):
    """Punto de una serie temporal de precio/km de un listing."""

    scraped_at: datetime
    price: float | None
    currency: str | None
    mileage: int | None


class VehicleDetail(VehicleRead):
    """Vehículo con sus anuncios ACTIVE (regla: el dashboard solo ve datos live)."""

    listings: list[ListingListItem]


class VehicleHistoryEntry(BaseModel):
    """Histórico de un anuncio del vehículo: serie completa de snapshots (append-only)."""

    listing_id: int
    source: str
    source_listing_id: str
    url: str | None
    status: str
    snapshots: list[PricePoint]


class MarketStats(BaseModel):
    """Estadísticas del mercado del vehículo (listings ACTIVE con precio conocido)."""

    vehicle_id: int
    count: int
    min_price: float | None
    p10: float | None
    p50: float | None
    p90: float | None
    max_price: float | None
    mean_price: float | None
    currency: str | None
