from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class ListingEventType(str, Enum):
    LISTED = "LISTED"
    PRICE_CHANGED = "PRICE_CHANGED"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"
    MILEAGE_CHANGED = "MILEAGE_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    REMOVED = "REMOVED"
    REAPPEARED = "REAPPEARED"


class ListingEvent(Base):
    """Registro de cambios importantes sobre un anuncio."""

    __tablename__ = "listing_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type: Mapped[ListingEventType] = mapped_column(
        SqlEnum(ListingEventType, native_enum=False, length=40, create_constraint=True),
        nullable=False,
    )

    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped["Listing"] = relationship(back_populates="events")
