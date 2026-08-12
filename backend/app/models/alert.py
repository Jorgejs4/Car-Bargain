"""Modelos de alertas y notificaciones (Fase 10).

Sin auth completa todavía: hay un único usuario implícito ("me"). Las
preferencias de alerta guardan los umbrales de rentabilidad/técnicos, y las
notificaciones se generan cuando un listing ACTIVE cumple todos los filtros.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NotificationStatus(str, Enum):
    PENDING = "pending"
    READ = "read"
    SENT = "sent"


class AlertPreference(Base):
    """Preferencias de alerta del usuario (una fila por usuario, aquí "me")."""

    __tablename__ = "alert_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default="me")

    # Presupuestos
    max_purchase_price: Mapped[float | None] = mapped_column(Float)
    max_total_cost: Mapped[float | None] = mapped_column(Float)

    # Rentabilidad
    min_profit: Mapped[float | None] = mapped_column(Float)
    min_roi: Mapped[float | None] = mapped_column(Float)
    min_bargain_score: Mapped[float | None] = mapped_column(Float)
    max_risk_score: Mapped[float | None] = mapped_column(Float)

    # Técnicos
    brands: Mapped[list | None] = mapped_column(JSONB)  # lista de marcas, vacía = todas
    fuel: Mapped[str | None] = mapped_column(String(30))
    transmission: Mapped[str | None] = mapped_column(String(30))
    max_mileage: Mapped[int | None] = mapped_column(Integer)
    year_min: Mapped[int | None] = mapped_column(Integer)

    # Región
    region: Mapped[str | None] = mapped_column(String(10))  # None=todas, "ES", "EU"

    # Canales
    notify_web: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notifications: Mapped[list["Notification"]] = relationship(back_populates="preference")


class Notification(Base):
    """Notificación de una ganga que cumple las preferencias del usuario."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    preference_id: Mapped[int] = mapped_column(
        ForeignKey("alert_preferences.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(JSONB)  # datos estructurados del deal

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NotificationStatus.PENDING.value, server_default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    preference: Mapped["AlertPreference"] = relationship(back_populates="notifications")
