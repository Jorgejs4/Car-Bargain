from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing_event import ListingEvent
    from app.models.listing_snapshot import ListingSnapshot
    from app.models.vehicle import Vehicle


class ListingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    REMOVED = "REMOVED"
    SOLD = "SOLD"


class Listing(Base):
    """Anuncio concreto de una fuente. Identidad: (source, source_listing_id)."""

    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_listing_id", name="uq_listings_source_listing_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), index=True
    )

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_listing_id: Mapped[str] = mapped_column(String(255), nullable=False)

    url: Mapped[str | None] = mapped_column(Text)
    seller_type: Mapped[str | None] = mapped_column(String(30))
    country: Mapped[str | None] = mapped_column(String(2))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[ListingStatus] = mapped_column(
        SqlEnum(ListingStatus, native_enum=False, length=30, create_constraint=True),
        nullable=False,
        default=ListingStatus.ACTIVE,
        server_default=ListingStatus.ACTIVE.value,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehicle: Mapped["Vehicle | None"] = relationship(back_populates="listings")
    snapshots: Mapped[list["ListingSnapshot"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    events: Mapped[list["ListingEvent"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
