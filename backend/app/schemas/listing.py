from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.listing import ListingStatus
from app.schemas.listing_event import ListingEventRead
from app.schemas.listing_snapshot import ListingSnapshotRead
from app.schemas.photo_analysis import PhotoAnalysisRead
from app.schemas.vehicle import VehicleRead


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int | None
    source: str
    source_listing_id: str
    url: str | None
    seller_type: str | None
    country: str | None
    first_seen_at: datetime
    last_seen_at: datetime | None
    is_historical: bool = False
    status: ListingStatus
    photo_signals: dict | None
    text_signals: dict | None
    needs_review: bool
    risk_score: float | None
    bargain_score: float | None
    absolute_margin: float | None
    predicted_price: float | None
    predicted_price_es: float | None
    cross_border_margin: float | None
    cross_border_score: float | None
    estimated_import_cost: float | None
    total_cost_es: float | None

    created_at: datetime
    updated_at: datetime


class ListingListItem(BaseModel):
    """Fila de la lista de listings: vehículo + último snapshot + señales (Fase 4)."""

    id: int
    source: str
    source_listing_id: str
    url: str | None
    seller_type: str | None
    country: str | None
    status: ListingStatus
    is_historical: bool = False

    brand: str | None
    model: str | None
    generation: str | None
    variant: str | None
    year: int | None
    fuel: str | None
    transmission: str | None
    power_kw: float | None

    title: str | None
    price: float | None
    currency: str | None
    mileage: int | None
    image_urls: list[str] = []
    comparison_count: int = 0
    archive_reason: str | None = None

    condition_signals: dict | None
    photo_signals: dict | None
    text_signals: dict | None
    needs_review: bool
    risk_score: float | None
    bargain_score: float | None
    absolute_margin: float | None
    predicted_price: float | None
    predicted_price_es: float | None
    cross_border_margin: float | None
    cross_border_score: float | None
    estimated_import_cost: float | None
    total_cost_es: float | None

    first_seen_at: datetime
    last_seen_at: datetime | None


class ListingDetail(ListingListItem):
    """Detalle de un listing: vehículo + serie de snapshots + eventos + análisis CV."""

    vehicle: VehicleRead | None
    current_snapshot: ListingSnapshotRead | None
    snapshots: list[ListingSnapshotRead]
    events: list[ListingEventRead]
    photo_analyses: list[PhotoAnalysisRead]
    import_breakdown: dict | None = None
    market: dict | None = None
