from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class Vehicle(Base):
    """Identidad normalizada del vehículo."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)

    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str | None] = mapped_column(String(150))
    generation: Mapped[str | None] = mapped_column(String(100))
    variant: Mapped[str | None] = mapped_column(String(150))

    year: Mapped[int | None] = mapped_column(Integer)
    registration_date: Mapped[date | None] = mapped_column(Date)

    fuel: Mapped[str | None] = mapped_column(String(50))
    transmission: Mapped[str | None] = mapped_column(String(50))
    drivetrain: Mapped[str | None] = mapped_column(String(50))

    power_kw: Mapped[Decimal | None] = mapped_column(Numeric)
    engine_cc: Mapped[int | None] = mapped_column(Integer)
    co2_g_km: Mapped[Decimal | None] = mapped_column(Numeric)

    body_type: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="vehicle")
