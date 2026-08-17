"""Schemas de alertas y notificaciones (Fase 10)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertPreferenceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    max_purchase_price: float | None = None
    max_total_cost: float | None = None
    min_profit: float | None = None
    min_roi: float | None = None
    min_bargain_score: float | None = None
    max_risk_score: float | None = None
    brands: list[str] | None = None
    fuel: str | None = None
    transmission: str | None = None
    max_mileage: int | None = None
    year_min: int | None = None
    region: str | None = None
    notify_web: bool = True
    notify_email: bool = False


class AlertPreferenceRead(AlertPreferenceBase):
    id: int
    user_key: str


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    title: str
    body: dict | None
    status: str
    created_at: datetime
