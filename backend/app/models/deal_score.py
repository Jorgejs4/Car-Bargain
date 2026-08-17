from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class DealScore(Base):
    __tablename__ = "deal_scores"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_deal_scores_listing"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    sale_value: Mapped[float | None] = mapped_column(Numeric)
    purchase_cost: Mapped[float | None] = mapped_column(Numeric)
    import_cost: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    repair_cost: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    preparation_cost: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    financing_cost: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    expected_profit: Mapped[float | None] = mapped_column(Numeric)
    roi: Mapped[float | None] = mapped_column(Numeric)
    score: Mapped[float | None] = mapped_column(Numeric)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    condition_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    listing: Mapped["Listing"] = relationship()
