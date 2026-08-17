from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ListingSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    scraped_at: datetime
    price: float | None
    currency: str | None
    mileage: int | None
    title: str | None
    description: str | None
    seller_comment: str | None
    description_es: str | None = None
    seller_comment_es: str | None = None
    seller_type: str | None
    location: str | None
    condition_signals: dict | None
    created_at: datetime
