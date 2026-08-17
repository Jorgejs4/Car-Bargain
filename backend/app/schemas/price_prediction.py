from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PricePredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    market: str
    p10: float | None
    p50: float | None
    p90: float | None
    confidence: str
    condition_bucket: str
    comparables_count: int
    model_version: str
    predicted_at: datetime
