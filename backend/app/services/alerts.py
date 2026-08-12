"""Motor de alertas (Fase 10): evalúa listings ACTIVE contra las preferencias.

Un listing genera notificación solo si cumple TODOS los filtros configurados
(presupuesto, rentabilidad, técnicos, región). Dedupe por `(preference_id,
listing_id)`: un deal nuevo se notifica una vez.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AlertPreference,
    Listing,
    ListingSnapshot,
    ListingStatus,
    Notification,
    NotificationStatus,
    Vehicle,
)

logger = logging.getLogger(__name__)

_EU_COUNTRIES = {"DE", "FR", "IT", "NL", "BE", "AT", "LU"}


@dataclass
class EvalResult:
    checked: int = 0
    matched: int = 0
    notified: int = 0
    deduped: int = 0


def _matches(pref: AlertPreference, li: Listing, vehicle: Vehicle | None, snap: ListingSnapshot | None) -> bool:
    """True si el listing cumple todos los filtros configurados (los None se ignoran)."""
    if snap is None or snap.price is None:
        return False

    price = float(snap.price)

    if pref.max_purchase_price is not None and price > pref.max_purchase_price:
        return False
    if (
        pref.max_total_cost is not None
        and li.total_cost_es is not None
        and li.total_cost_es > pref.max_total_cost
    ):
        return False

    if (
        pref.min_profit is not None
        and li.absolute_margin is not None
        and li.absolute_margin < pref.min_profit
    ):
        return False
    if (
        pref.min_roi is not None
        and li.absolute_margin is not None
    ):
        roi = li.absolute_margin / price if price > 0 else 0.0
        if roi < pref.min_roi:
            return False
    if (
        pref.min_bargain_score is not None
        and li.bargain_score is not None
        and li.bargain_score < pref.min_bargain_score
    ):
        return False
    if (
        pref.max_risk_score is not None
        and li.risk_score is not None
        and float(li.risk_score) > pref.max_risk_score
    ):
        return False

    if pref.brands:
        brand = (vehicle.brand if vehicle else None) or ""
        if brand.lower() not in {b.lower() for b in pref.brands}:
            return False
    if pref.fuel and (not vehicle or (vehicle.fuel or "").lower() != pref.fuel.lower()):
        return False
    if pref.transmission and (not vehicle or (vehicle.transmission or "").lower() != pref.transmission.lower()):
        return False
    if (
        pref.max_mileage is not None
        and snap.mileage is not None
        and snap.mileage > pref.max_mileage
    ):
        return False
    if (
        pref.year_min is not None
        and vehicle
        and vehicle.year is not None
        and vehicle.year < pref.year_min
    ):
        return False

    if pref.region == "ES" and li.country != "ES":
        return False
    return not (pref.region == "EU" and (li.country or "") not in _EU_COUNTRIES)


def _build_notification(pref: AlertPreference, li: Listing, vehicle: Vehicle | None, snap: ListingSnapshot) -> tuple[str, dict]:
    brand = vehicle.brand if vehicle else None
    model = vehicle.model if vehicle else None
    title = " ".join(p for p in (brand, model) if p) or f"Anuncio {li.id}"
    body = {
        "brand": brand,
        "model": model,
        "year": vehicle.year if vehicle else None,
        "country": li.country,
        "price": float(snap.price) if snap.price is not None else None,
        "absolute_margin": li.absolute_margin,
        "bargain_score": li.bargain_score,
        "cross_border_margin": li.cross_border_margin,
        "total_cost_es": li.total_cost_es,
        "risk_score": float(li.risk_score) if li.risk_score is not None else None,
        "url": li.url,
        "listing_id": li.id,
    }
    return title, body


def evaluate_alerts(session: Session, user_key: str = "me") -> EvalResult:
    """Evalúa todos los listings ACTIVE contra las preferencias del usuario."""
    result = EvalResult()

    pref = session.scalar(select(AlertPreference).where(AlertPreference.user_key == user_key))
    if pref is None:
        return result

    listings = session.scalars(
        select(Listing).where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.is_historical.is_(False),
        )
    ).all()

    for li in listings:
        result.checked += 1
        snap = session.scalar(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == li.id)
            .order_by(ListingSnapshot.scraped_at.desc())
            .limit(1)
        )
        vehicle = session.get(Vehicle, li.vehicle_id) if li.vehicle_id else None

        if not _matches(pref, li, vehicle, snap):
            continue
        result.matched += 1

        exists = session.scalar(
            select(Notification).where(
                Notification.preference_id == pref.id,
                Notification.listing_id == li.id,
            )
        )
        if exists is not None:
            result.deduped += 1
            continue

        title, body = _build_notification(pref, li, vehicle, snap)
        session.add(
            Notification(
                preference_id=pref.id,
                listing_id=li.id,
                title=title,
                body=body,
                status=NotificationStatus.PENDING.value,
            )
        )
        result.notified += 1

    return result
