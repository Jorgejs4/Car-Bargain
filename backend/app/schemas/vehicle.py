from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class VehicleBase(BaseModel):
    brand: str
    model: str | None = None
    generation: str | None = None
    variant: str | None = None
    year: int | None = None
    registration_date: date | None = None
    fuel: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None
    power_kw: float | None = None
    engine_cc: int | None = None
    co2_g_km: float | None = None
    body_type: str | None = None


class VehicleCreate(VehicleBase):
    pass


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
