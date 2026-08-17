from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class ListingSnapshot(Base):
    """Estado de un anuncio en un momento dado. SOLO append: nunca sobrescribir."""

    __tablename__ = "listing_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    mileage: Mapped[int | None] = mapped_column(Integer)

    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    seller_comment: Mapped[str | None] = mapped_column(Text)

    seller_type: Mapped[str | None] = mapped_column(String(30))

    location: Mapped[str | None] = mapped_column(Text)

    condition_signals: Mapped[dict | None] = mapped_column(JSONB)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped["Listing"] = relationship(back_populates="snapshots")
