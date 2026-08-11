from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.listing_event import ListingEventType


class ListingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    event_type: ListingEventType
    event_timestamp: datetime
    old_value: dict | None
    new_value: dict | None
