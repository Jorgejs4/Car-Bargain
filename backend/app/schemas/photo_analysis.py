from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PhotoAnalysisResult(BaseModel):
    """Resultado del clasificador de una imagen (frontera del motor CV, no del ORM)."""

    label: str
    probability: float
    model_version: str


class PhotoAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    image_url: str
    local_path: str | None
    label: str | None
    probability: Decimal | None
    model_version: str | None
    analyzed_at: datetime
    created_at: datetime
