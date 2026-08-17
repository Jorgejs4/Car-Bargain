from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class PricePrediction(Base):
    __tablename__ = "price_predictions"
    __table_args__ = (UniqueConstraint("listing_id", "market", name="uq_price_predictions_listing_market"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    p10: Mapped[float | None] = mapped_column(Numeric)
    p50: Mapped[float | None] = mapped_column(Numeric)
    p90: Mapped[float | None] = mapped_column(Numeric)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    condition_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    comparables_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    listing: Mapped["Listing"] = relationship()
