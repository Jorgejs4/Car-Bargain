from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.listing import ListingStatus


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
    status: ListingStatus
    photo_signals: dict | None
    needs_review: bool
    risk_score: Decimal | None
    created_at: datetime
    updated_at: datetime
