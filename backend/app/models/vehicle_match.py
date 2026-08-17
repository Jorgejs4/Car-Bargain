from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing


class VehicleMatch(Base):
    """Registro de matching de un listing a un vehículo (Fase 5).

    Guarda la traza de cómo se resolvió la identidad: valores raw vs
    normalizados, estrategia, confianza y fuente. Append-only, una fila por
    listing (se actualiza cuando una nueva ingesta cambia la asignación).
    """

    __tablename__ = "vehicle_matches"

    id: Mapped[int] = mapped_column(primary_key=True)

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    raw_value: Mapped[dict | None] = mapped_column(JSONB)
    normalized_value: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped["Listing"] = relationship(back_populates="vehicle_match")
