from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class PhotoAnalysis(Base):
    """Resultado del análisis de daño visual (CLIP zero-shot) de una foto de un anuncio."""

    __tablename__ = "photo_analyses"
    __table_args__ = (
        UniqueConstraint("listing_id", "image_url", name="uq_photo_analyses_listing_image"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)

    label: Mapped[str | None] = mapped_column(String(50))
    probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    model_version: Mapped[str | None] = mapped_column(String(100))

    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped["Listing"] = relationship(back_populates="photo_analyses")
