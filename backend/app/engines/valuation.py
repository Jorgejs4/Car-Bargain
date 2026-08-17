"""Motor de valoración dual por comparables jerárquicos (Fase 6 v6).

El usuario detectó que las predicciones anteriores eran irreales: mezclaban
los mercados ES y EU en un único modelo y la regresión lineal global producía
precios sin relación con la media real de los anuncios.

Esta versión NO usa regresión global. Entrena **dos motores por comparables**:

  - Motor Español (es): entrenado solo con listings ES.
  - Motor Europeo (eu): entrenado solo con listings NO-ES (NL, DE, FR, IT…).

Cada listing obtiene dos valoraciones:

  - `predicted_price_es`: lo que vale esa unidad en el mercado español.
  - `predicted_price_eu`:  lo que vale esa unidad en el mercado europeo.

Para cada listing se usa el motor de SU mercado:

  - listing ES → `bargain_score`/`absolute_margin` con el motor español.
  - listing EU → `bargain_score`/`absolute_margin` con el motor europeo.

El margen cross-border (chollo de importación) = valor en España
(`predicted_price_es`) menos el coste total de traerlo a España
(`total_cost_es` = precio + costes de importación). Solo se muestra para
listings no-ES y con comparables en el mercado español (confianza media+).

Confianza por motor (jerárquica, igual que un tasador):
  alta:   mismo brand+model, edad ±2 años → mediana
  sin:    sin comparables estrictos → `None` (la UI muestra "sin valoración").

Solo se usan señales textuales del anuncio para separar unidades con averías.
El CV no participa en la valoración. Solo se publican márgenes con dos
comparables estrictos como mínimo.
"""

import logging
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingSnapshot, ListingStatus, Vehicle

logger = logging.getLogger(__name__)

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_NONE = "none"

_CURRENT_YEAR = 2026
_YEAR_RATE = 0.07          # ~7% de depreciación por año
_KM_RATE_PER_10K = 0.03    # ~3% del precio por cada 10.000 km de más


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _key(value: str | None) -> str:
    return (value or "").strip().lower()


class ComparablesValuation:
    """Valora por comparables jerárquicos de UN mercado; devuelve (precio, confianza)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.trained_at: datetime | None = None

    def fit(self, rows: list[dict]) -> bool:
        if len(rows) < 3:
            logger.warning("ComparablesValuation.fit: solo %d filas", len(rows))
            return False
        self.rows = rows
        self.trained_at = datetime.now(timezone.utc)
        return True

    def _candidates(
        self,
        my_id: int,
        brand: str | None,
        model: str | None,
        year: int,
        *,
        same_model: bool = True,
        age_window: int | None = 2,
    ) -> list[dict]:
        out: list[dict] = []
        for r in self.rows:
            if r["listing_id"] == my_id:
                continue
            if _key(r.get("brand")) != brand:
                continue
            if same_model and _key(r.get("model")) != model:
                continue
            if age_window is not None:
                r_year = r.get("year") or 0
                if not r_year or abs(r_year - year) > age_window:
                    continue
            signals = r.get("text_signals") or {}
            if signals.get("has_problem") is True:
                continue
            out.append(r)
        return out

    def predict(self, row: dict) -> tuple[float | None, str]:
        if not self.rows:
            return None, CONFIDENCE_NONE

        my_id = row["listing_id"]
        brand = _key(row.get("brand"))
        model = _key(row.get("model"))
        year = row.get("year") or 0

        comps = self._candidates(my_id, brand, model, year)
        if len(comps) < 2:
            return None, CONFIDENCE_NONE
        return self._adjusted_median(comps, row), CONFIDENCE_HIGH

    def _adjusted_median(self, comps: list[dict], row: dict) -> float:
        base = _median([c["price"] for c in comps])
        ref_year = _median([c["year"] for c in comps if c["year"]]) or (row.get("year") or 0)
        ref_km = _median([c["km"] for c in comps if c["km"]]) or (row.get("km") or 0)
        year = row.get("year") or 0
        km = row.get("km") or 0

        price = base
        if ref_year and year:
            price *= 1.0 + _YEAR_RATE * (year - ref_year)
        if ref_km and km:
            price *= 1.0 - _KM_RATE_PER_10K * ((km - ref_km) / 10000.0)
        return max(500.0, price)


class DualMarketValuation:
    """Dos motores: español y europeo (excluye España)."""

    def __init__(self) -> None:
        self.es: ComparablesValuation = ComparablesValuation()
        self.eu: ComparablesValuation = ComparablesValuation()

    def fit(self, rows: list[dict]) -> bool:
        es_rows = [r for r in rows if _key(r.get("country")) == "es"]
        eu_rows = [r for r in rows if _key(r.get("country")) != "es"]
        es_ok = self.es.fit(es_rows)
        eu_ok = self.eu.fit(eu_rows)
        logger.info(
            "DualMarketValuation.fit: es=%d(%s) eu=%d(%s)",
            len(es_rows), "ok" if es_ok else "insuficiente",
            len(eu_rows), "ok" if eu_ok else "insuficiente",
        )
        return es_ok or eu_ok


_model: DualMarketValuation | None = None


def get_model() -> DualMarketValuation:
    global _model
    if _model is None:
        _model = DualMarketValuation()
    return _model


def fetch_training_rows(session: Session) -> list[dict]:
    """Filas de entrenamiento: ACTIVE + STALE (no históricos) con snapshot.

    STALE son anuncios recientes que llevan >6h sin verse; su último precio
    sigue siendo un dato real del mercado, así que sirven para entrenar.
    """
    listings = session.scalars(
        select(Listing).where(
            Listing.status.in_([ListingStatus.ACTIVE, ListingStatus.STALE]),
            Listing.is_historical.is_(False),
        )
    ).all()
    rows: list[dict] = []
    for li in listings:
        snap = session.scalar(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == li.id)
            .order_by(ListingSnapshot.scraped_at.desc())
            .limit(1)
        )
        if snap is None or snap.price is None:
            continue
        vehicle = session.get(Vehicle, li.vehicle_id) if li.vehicle_id else None
        rows.append({
            "listing_id": li.id,
            "country": li.country,
            "price": float(snap.price),
            "km": float(snap.mileage) if snap.mileage else 0.0,
            "year": vehicle.year if vehicle and vehicle.year else 0,
            "fuel": vehicle.fuel if vehicle else None,
            "transmission": vehicle.transmission if vehicle else None,
            "brand": vehicle.brand if vehicle else None,
            "model": vehicle.model if vehicle else None,
            "text_signals": li.text_signals,
        })
    return rows


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 0.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot


def score_all(session: Session) -> dict:
    """Valora listings con dos motores (ES y EU). Margen solo con confianza alta/media."""
    import time

    started = time.monotonic()
    rows = fetch_training_rows(session)
    model = get_model()
    trained = model.fit(rows)
    if not trained:
        return {"trained": False, "scored": 0, "r2": None, "mape": None, "duration_ms": 0}

    scored = 0
    high = medium = none = 0
    y_eval: list[float] = []
    p_eval: list[float] = []

    for row in rows:
        listing = session.get(Listing, row["listing_id"])
        if listing is None:
            continue
        is_es = _key(row.get("country")) == "es"
        own = model.es if is_es else model.eu

        predicted, confidence = own.predict(row)
        if predicted is None or confidence == CONFIDENCE_NONE:
            listing.predicted_price = None
            listing.bargain_score = None
            listing.absolute_margin = None
            none += 1
        else:
            if (row.get("text_signals") or {}).get("has_problem") is True:
                predicted *= 0.85
            actual = row["price"]
            listing.predicted_price = round(predicted, 2)
            listing.bargain_score = round((predicted - actual) / predicted, 6)
            listing.absolute_margin = round(predicted - actual, 2)
            scored += 1
            y_eval.append(actual)
            p_eval.append(predicted)
            if confidence == CONFIDENCE_HIGH:
                high += 1
            else:
                medium += 1

        # Valor en mercado español (para chollos de importación).
        es_pred, es_conf = model.es.predict(row)
        if es_pred is None or es_conf == CONFIDENCE_NONE:
            listing.predicted_price_es = None
        else:
            if (row.get("text_signals") or {}).get("has_problem") is True:
                es_pred *= 0.85
            listing.predicted_price_es = round(es_pred, 2)

    y = np.array(y_eval)
    y_pred = np.array(p_eval)
    r2 = _r2_score(y, y_pred) if len(y) else None
    mape = float(np.mean(np.abs(y_pred - y) / np.maximum(y, 1.0))) if len(y) else None

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "score_all: %d con margen (alta=%d media=%d), %d sin valoración, R²=%s MAPE=%s (%d ms)",
        scored, high, medium, none,
        f"{r2:.3f}" if r2 is not None else "n/a",
        f"{mape*100:.1f}%" if mape is not None else "n/a",
        duration_ms,
    )
    return {
        "trained": True,
        "scored": scored,
        "high_confidence": high,
        "medium_confidence": medium,
        "no_confidence": none,
        "r2": round(r2, 4) if r2 is not None else None,
        "mape": round(mape, 4) if mape is not None else None,
        "duration_ms": duration_ms,
    }
