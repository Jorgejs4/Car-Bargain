from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DealScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    listing_id: int
    sale_value: float | None
    purchase_cost: float | None
    import_cost: float
    repair_cost: float
    preparation_cost: float
    financing_cost: float
    expected_profit: float | None
    roi: float | None
    score: float | None
    confidence: str
    condition_bucket: str
    model_version: str
    calculated_at: datetime
