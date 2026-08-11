from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ListingSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    scraped_at: datetime
    price: Decimal | None
    currency: str | None
    mileage: int | None
    title: str | None
    description: str | None
    seller_type: str | None
    location: str | None
    condition_signals: dict | None
    created_at: datetime
