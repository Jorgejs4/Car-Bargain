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
  media:  misma marca, edad ±2 años → mediana
  sin:    sin comparables cercanos → `None` (la UI muestra "sin valoración").

El daño visual (CV) reduce un 15% el valor antes de comparar. Solo se
publican márgenes con confianza alta o media.
"""

import logging
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingSnapshot, ListingStatus, PricePrediction, Vehicle

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
        same_model: bool,
        age_window: int | None,
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
            out.append(r)
        return out

    def predict(self, row: dict) -> tuple[float | None, str]:
        if not self.rows:
            return None, CONFIDENCE_NONE

        my_id = row["listing_id"]
        brand = _key(row.get("brand"))
        model = _key(row.get("model"))
        year = row.get("year") or 0

        levels = [
            (True, 2, CONFIDENCE_HIGH),
            (True, None, CONFIDENCE_MEDIUM),
            (False, 2, CONFIDENCE_MEDIUM),
        ]
        for same_model, age_window, confidence in levels:
            comps = self._candidates(
                my_id, brand, model, year,
                same_model=same_model, age_window=age_window,
            )
            if len(comps) >= 2:
                return self._adjusted_median(comps, row), confidence

        # Misma marca, cualquier edad → solo referencia, sin publicar margen.
        comps = self._candidates(
            my_id, brand, model, year,
            same_model=False, age_window=None,
        )
        if len(comps) >= 3:
            return self._adjusted_median(comps, row), CONFIDENCE_NONE

        return None, CONFIDENCE_NONE

    def predict_distribution(self, row: dict) -> tuple[float | None, str, float | None, float | None, int]:
        brand = _key(row.get("brand")); model = _key(row.get("model")); year = row.get("year") or 0
        for same_model, age_window, confidence in [(True, 2, CONFIDENCE_HIGH), (True, None, CONFIDENCE_MEDIUM), (False, 2, CONFIDENCE_MEDIUM)]:
            comps = self._candidates(row["listing_id"], brand, model, year, same_model=same_model, age_window=age_window)
            if len(comps) >= 2:
                prices = np.array([c["price"] for c in comps], dtype=float)
                return (
                    self._adjusted_median(comps, row), confidence,
                    self._adjusted_value(comps, row, float(np.quantile(prices, 0.10))),
                    self._adjusted_value(comps, row, float(np.quantile(prices, 0.90))),
                    len(comps),
                )
        return None, CONFIDENCE_NONE, None, None, 0

    def _adjusted_median(self, comps: list[dict], row: dict) -> float:
        base = _median([c["price"] for c in comps])
        return self._adjusted_value(comps, row, base)

    def _adjusted_value(self, comps: list[dict], row: dict, base: float) -> float:
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
            "photo_signals": li.photo_signals,
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

        predicted, confidence, p10, p90, comparables_count = own.predict_distribution(row)
        condition_bucket = _condition_bucket(row)
        market = "es" if is_es else "eu"
        adjustment = _condition_adjustment(condition_bucket)
        _save_prediction(session, row["listing_id"], market, p10 * adjustment if p10 is not None else None, predicted * adjustment if predicted is not None else None, p90 * adjustment if p90 is not None else None, confidence, condition_bucket, comparables_count)
        if predicted is None or confidence == CONFIDENCE_NONE:
            listing.predicted_price = None
            listing.bargain_score = None
            listing.absolute_margin = None
            none += 1
        else:
            predicted *= _condition_adjustment(condition_bucket)
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
        es_pred, es_conf, es_p10, es_p90, es_count = model.es.predict_distribution(row)
        if not is_es:
            adjustment = _condition_adjustment(condition_bucket)
            _save_prediction(session, row["listing_id"], "es", es_p10 * adjustment if es_p10 is not None else None, es_pred * adjustment if es_pred is not None else None, es_p90 * adjustment if es_p90 is not None else None, es_conf, condition_bucket, es_count)
        if es_pred is None or es_conf == CONFIDENCE_NONE:
            listing.predicted_price_es = None
        else:
            es_pred *= _condition_adjustment(condition_bucket)
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


def _condition_bucket(row: dict) -> str:
    text = row.get("text_signals") or {}
    photo = row.get("photo_signals") or {}
    if any(text.get(key) for key in ("has_accident", "has_engine_issue", "has_mechanical_issue", "has_gearbox_issue", "has_fire_or_flood_damage", "not_running")) or photo.get("has_visible_damage"):
        return "significant"
    if text.get("has_rust") or text.get("has_repaint") or text.get("has_cosmetic_damage") or photo.get("cosmetic_defects"):
        return "cosmetic"
    if text.get("detail_fetched") or text.get("description_available"):
        return "damage_free"
    return "unknown"


def _condition_adjustment(bucket: str) -> float:
    return {"significant": 0.85, "cosmetic": 0.95}.get(bucket, 1.0)


def _save_prediction(session: Session, listing_id: int, market: str, p10: float | None, p50: float | None, p90: float | None, confidence: str, condition_bucket: str, comparables_count: int) -> None:
    prediction = session.scalar(select(PricePrediction).where(PricePrediction.listing_id == listing_id, PricePrediction.market == market))
    if prediction is None:
        prediction = PricePrediction(listing_id=listing_id, market=market)
        session.add(prediction)
    prediction.p10 = round(p10, 2) if p10 is not None else None
    prediction.p50 = round(p50, 2) if p50 is not None else None
    prediction.p90 = round(p90, 2) if p90 is not None else None
    prediction.confidence = confidence
    prediction.condition_bucket = condition_bucket
    prediction.comparables_count = comparables_count
    prediction.model_version = "comparables-v7"
    prediction.predicted_at = datetime.now(timezone.utc)
