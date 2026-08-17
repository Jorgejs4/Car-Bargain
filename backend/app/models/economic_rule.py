from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaxRule(Base):
    __tablename__ = "tax_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    co2_max: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)


class TransportRate(Base):
    __tablename__ = "transport_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_country: Mapped[str] = mapped_column(String(2), nullable=False)
    target_country: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)


class RepairEstimate(Base):
    __tablename__ = "repair_estimates"
    id: Mapped[int] = mapped_column(primary_key=True)
    damage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    min_cost: Mapped[float] = mapped_column(Float, nullable=False)
    max_cost: Mapped[float] = mapped_column(Float, nullable=False)
    expected_cost: Mapped[float] = mapped_column(Float, nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
