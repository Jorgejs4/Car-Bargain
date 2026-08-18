from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing_event import ListingEvent
    from app.models.listing_snapshot import ListingSnapshot
    from app.models.photo_analysis import PhotoAnalysis
    from app.models.vehicle import Vehicle
    from app.models.vehicle_match import VehicleMatch


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
    # Evidencia de ausencias únicamente de reconciliaciones completas de la fuente.
    consecutive_misses: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_missed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # True si el anuncio proviene de una fuente histórica (p. ej. Wayback Machine),
    # no del scrape en vivo. Los históricos nunca aparecen en el panel de activos.
    is_historical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    status: Mapped[ListingStatus] = mapped_column(
        SqlEnum(ListingStatus, native_enum=False, length=30, create_constraint=True),
        nullable=False,
        default=ListingStatus.ACTIVE,
        server_default=ListingStatus.ACTIVE.value,
        index=True,
    )

    # Agregado de daño visual (CV, Fase 3): photo_damage_prob / has_visible_damage / damage_types.
    photo_signals: Mapped[dict | None] = mapped_column(JSONB)
    # Agregado de análisis del título + descripción más recientes.
    # `deal_eligible` solo es true cuando hay descripción y no se detecta un
    # problema textual explícito; ausencia de evidencia queda en unknown.
    text_signals: Mapped[dict | None] = mapped_column(JSONB)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    # Score de oportunidad (Fase 6): positivo = por debajo del P50 de mercado
    # considerando precio, km, año y daños. Null si aún no se ha calculado.
    bargain_score: Mapped[float | None] = mapped_column(index=True)

    # Margen absoluto en € (predicho - real) y precio predicho por el modelo
    # del mercado propio del listing (motor ES para ES, motor EU para el resto).
    absolute_margin: Mapped[float | None] = mapped_column()
    predicted_price: Mapped[float | None] = mapped_column()

    # Valor estimado de esa unidad en el mercado español (motor ES).
    # Se usa para detectar chollos de importación: si un listing EU vale X en
    # España y cuesta X - gastos traerlo, hay margen de importación.
    predicted_price_es: Mapped[float | None] = mapped_column(index=True)

    # Fase 9: margen cross-border (€) y score (%) descontando costes de importación.
    # Positivo = incluso importándolo, el precio total está por debajo del valor de mercado.
    cross_border_margin: Mapped[float | None] = mapped_column(index=True)
    cross_border_score: Mapped[float | None] = mapped_column()

    # Fase 7: coste estimado de importación a España y precio total puesto en ES.
    estimated_import_cost: Mapped[float | None] = mapped_column()
    total_cost_es: Mapped[float | None] = mapped_column(index=True)

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
    photo_analyses: Mapped[list["PhotoAnalysis"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    vehicle_match: Mapped["VehicleMatch | None"] = relationship(back_populates="listing", uselist=False)
