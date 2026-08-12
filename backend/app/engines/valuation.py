"""Motor de valoración: predicción de precio justo en dos etapas.

Fase 6 v2: en lugar de una regresión ciega a la marca, primero se calcula un
precio base por marca (mediana de los precios de esa marca en el mercado). La
regresión lineal modela solo la desviación respecto a ese precio base según
año, km, combustible, cambio y daños.

Esto evita que un Smart y un Mercedes con el mismo año/km reciban la misma
predicción: el Smart parte de ~15 k€ y el Mercedes de ~40 k€.

El `bargain_score` final es (precio_predicho - precio_real) / precio_predicho.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingSnapshot, ListingStatus, Vehicle

logger = logging.getLogger(__name__)

_FUEL_FEATURES = ["petrol", "diesel", "electric", "hybrid", "lpg", "cng", "hydrogen"]
_NUMERIC_FEATURE_COUNT = 2  # year, mileage_km


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _fit_linear(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


class ValuationModel:
    """Modelo en dos etapas: baseline por marca + regresión sobre residuos."""

    def __init__(self):
        self.brand_baseline: dict[str, float] = {}
        self.default_baseline: float = 0.0
        self.coefs: np.ndarray | None = None
        self.feature_names: list[str] = []
        self.X_mean: np.ndarray | None = None
        self.X_std: np.ndarray | None = None
        self.trained_at: datetime | None = None

    def _build_features(self, row: dict) -> list[float]:
        f: list[float] = []
        self.feature_names = ["year", "mileage_km"]

        f.append(float(row.get("year", 0) or 0))
        f.append(float(row.get("mileage", 0) or 0))

        fuel = (row.get("fuel") or "").lower()
        for feat in _FUEL_FEATURES:
            self.feature_names.append(f"fuel_{feat}")
            f.append(1.0 if fuel == feat else 0.0)

        trans = (row.get("transmission") or "").lower()
        for t in ["manual", "automatic"]:
            self.feature_names.append(f"transmission_{t}")
            f.append(1.0 if trans == t else 0.0)

        has_damage = bool((row.get("photo_signals") or {}).get("has_visible_damage"))
        self.feature_names.append("has_damage")
        f.append(1.0 if has_damage else 0.0)

        self.feature_names.append("intercept")
        f.append(1.0)
        return f

    def _compute_baselines(self, rows: list[dict]) -> dict[str, float]:
        """Mediana de precio por marca (normalizada a minúsculas)."""
        by_brand: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            brand = (r.get("brand") or "").strip().lower()
            if brand:
                by_brand[brand].append(r["price"])
        baselines = {}
        for brand, prices in by_brand.items():
            baselines[brand] = _median(prices)
        all_prices = [r["price"] for r in rows]
        self.default_baseline = _median(all_prices) if all_prices else 0.0
        return baselines

    def fit(self, rows: list[dict]) -> bool:
        if len(rows) < 10:
            logger.warning("ValuationModel.fit: solo %d filas, se necesitan ≥10", len(rows))
            return False

        self.brand_baseline = self._compute_baselines(rows)

        # Construir features y target como residuo sobre el baseline de marca
        raw_features = []
        residuals = []
        for r in rows:
            brand = (r.get("brand") or "").strip().lower()
            baseline = self.brand_baseline.get(brand, self.default_baseline)
            raw_features.append(self._build_features(r))
            residuals.append(r["price"] - baseline)

        X_raw = np.array(raw_features, dtype=np.float64)
        y = np.array(residuals, dtype=np.float64)

        self.X_mean = np.zeros(X_raw.shape[1])
        self.X_std = np.ones(X_raw.shape[1])
        X = X_raw.copy()
        for j in range(min(_NUMERIC_FEATURE_COUNT, X.shape[1])):
            col = X[:, j]
            mean_j = float(np.mean(col))
            std_j = float(np.std(col))
            self.X_mean[j] = mean_j
            self.X_std[j] = std_j if std_j > 0 else 1.0
            X[:, j] = (col - mean_j) / self.X_std[j]

        self.coefs = _fit_linear(X, y)
        self.trained_at = datetime.now(timezone.utc)

        # Reconstruir predicciones completas para calcular R²
        y_pred_full = np.array([self._full_predict(r) or 0.0 for r in rows])
        y_full = np.array([r["price"] for r in rows])
        r2 = _r2_score(y_full, y_pred_full)

        logger.info(
            "ValuationModel entrenado: %d filas, %d marcas, %d features, R²=%.3f",
            len(rows),
            len(self.brand_baseline),
            len(self.feature_names),
            r2,
        )
        return True

    def _full_predict(self, row: dict) -> float | None:
        """Predicción completa: baseline marca + modelo residual."""
        if self.coefs is None:
            return None
        brand = (row.get("brand") or "").strip().lower()
        baseline = self.brand_baseline.get(brand, self.default_baseline)

        raw = np.array(self._build_features(row), dtype=np.float64)
        x = raw.copy()
        for j in range(min(_NUMERIC_FEATURE_COUNT, x.shape[0])):
            x[j] = (raw[j] - self.X_mean[j]) / self.X_std[j]

        residual = float(x @ self.coefs)
        return max(500.0, baseline + residual)

    def predict(self, row: dict) -> float | None:
        return self._full_predict(row)


_model: ValuationModel | None = None


def get_model() -> ValuationModel:
    global _model
    if _model is None:
        _model = ValuationModel()
    return _model


def fetch_training_rows(session: Session) -> list[dict]:
    """Recoge las filas de entrenamiento: listings ACTIVE no históricos con snapshot."""
    listings = session.scalars(
        select(Listing)
        .where(
            Listing.status == ListingStatus.ACTIVE,
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
            "price": float(snap.price),
            "mileage": float(snap.mileage) if snap.mileage else 0.0,
            "year": vehicle.year if vehicle and vehicle.year else 0,
            "fuel": vehicle.fuel if vehicle else None,
            "transmission": vehicle.transmission if vehicle else None,
            "brand": vehicle.brand if vehicle else None,
            "photo_signals": li.photo_signals,
        })
    return rows


def score_all(session: Session) -> dict:
    import time

    started = time.monotonic()
    rows = fetch_training_rows(session)
    model = get_model()
    trained = model.fit(rows)

    if not trained:
        return {"trained": False, "scored": 0, "r2": None, "duration_ms": 0}

    scored = 0
    for row in rows:
        listing_id = row["listing_id"]
        predicted = model.predict(row)
        if predicted is None or predicted == 0:
            continue
        actual = row["price"]
        rel_margin = (predicted - actual) / predicted
        abs_margin = predicted - actual
        listing = session.get(Listing, listing_id)
        if listing is not None:
            listing.bargain_score = round(rel_margin, 6)
            listing.absolute_margin = round(abs_margin, 2)
            listing.predicted_price = round(predicted, 2)
            scored += 1

    y = np.array([float(r["price"]) for r in rows])
    y_pred = np.array([model.predict(r) or 0.0 for r in rows])
    r2 = _r2_score(y, y_pred)

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("score_all: %d puntuados, R²=%.3f (%d ms)", scored, r2, duration_ms)
    return {"trained": True, "scored": scored, "r2": round(r2, 4), "duration_ms": duration_ms}
