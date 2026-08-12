"""Motor de valoración: predicción de precio justo por regresión lineal.

Fase 6: en lugar del simple ranking P50, este motor entrena un modelo de
regresión lineal multivariable con los listings ACTIVE y predice cuál
*debería* ser el precio de cada coche dados su año, km, combustible, cambio,
marca y estado visual (daños CV).

El `bargain_score` final es (precio_predicho - precio_real) / precio_predicho:
positivo → está más barato de lo que el modelo espera → posible ganga.
"""

import logging
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingSnapshot, ListingStatus, Vehicle

logger = logging.getLogger(__name__)

# Combustibles que el modelo distingue (el resto colapsa a "other").
_FUEL_FEATURES = ["petrol", "diesel", "electric", "hybrid", "lpg", "cng", "hydrogen"]


def _fit_linear(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Min-cuadrados: resuelve X·θ = y."""
    return np.linalg.lstsq(X, y, rcond=None)[0]


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


_NUMERIC_FEATURE_COUNT = 2  # year, mileage_km (primeras columnas)


class ValuationModel:
    """Predice el precio justo de un coche a partir de sus características."""

    def __init__(self):
        self.coefs: np.ndarray | None = None
        self.feature_names: list[str] = []
        self.X_mean: np.ndarray | None = None
        self.X_std: np.ndarray | None = None
        self.trained_at: datetime | None = None

    def _build_features(self, row: dict) -> list[float]:
        """Convierte una fila (snapshot + vehicle + listing) en vector de features."""
        f: list[float] = []
        self.feature_names = ["year", "mileage_km"]

        # Numéricas (se normalizan por el llamador)
        f.append(float(row.get("year", 0) or 0))
        f.append(float(row.get("mileage", 0) or 0))

        # Combustible one-hot
        fuel = (row.get("fuel") or "").lower()
        for feat in _FUEL_FEATURES:
            self.feature_names.append(f"fuel_{feat}")
            f.append(1.0 if fuel == feat else 0.0)

        # Cambio one-hot
        trans = (row.get("transmission") or "").lower()
        for t in ["manual", "automatic"]:
            self.feature_names.append(f"transmission_{t}")
            f.append(1.0 if trans == t else 0.0)

        # Daño visible (CV)
        has_damage = bool((row.get("photo_signals") or {}).get("has_visible_damage"))
        self.feature_names.append("has_damage")
        f.append(1.0 if has_damage else 0.0)

        # Intercept
        self.feature_names.append("intercept")
        f.append(1.0)

        return f

    def fit(self, rows: list[dict]) -> bool:
        """Entrena el modelo de regresión con las filas dadas.

        Cada fila debe tener: price, year, mileage, fuel, transmission,
        photo_signals, brand.
        Retorna False si no hay datos suficientes.
        """
        if len(rows) < 10:
            logger.warning("ValuationModel.fit: solo %d filas, se necesitan ≥10", len(rows))
            return False

        # Construir matriz de features y vector de precios
        raw_features = [self._build_features(r) for r in rows]
        X_raw = np.array(raw_features, dtype=np.float64)
        y = np.array([float(r["price"]) for r in rows], dtype=np.float64)

        # Normalizar solo las features numéricas (año, km); las categóricas
        # (one-hot) y el intercept se dejan en su escala original.
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

        y_pred = X @ self.coefs
        r2 = _r2_score(y, y_pred)
        logger.info(
            "ValuationModel entrenado: %d filas, %d features, R²=%.3f",
            len(rows),
            len(self.feature_names),
            r2,
        )
        return True

    def predict(self, row: dict) -> float | None:
        """Predice el precio justo para una fila. None si el modelo no está entrenado."""
        if self.coefs is None or self.X_mean is None or self.X_std is None:
            return None
        raw = np.array(self._build_features(row), dtype=np.float64)
        x = raw.copy()
        for j in range(min(_NUMERIC_FEATURE_COUNT, x.shape[0])):
            x[j] = (raw[j] - self.X_mean[j]) / self.X_std[j]
        return max(0.0, float(x @ self.coefs))


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
    """Entrena el modelo y puntúa todos los listings ACTIVE no históricos.

    Retorna {"trained": bool, "scored": int, "r2": float | None, "duration_ms": int}.
    """
    import time

    started = time.monotonic()
    rows = fetch_training_rows(session)
    model = get_model()
    trained = model.fit(rows)

    if not trained:
        return {"trained": False, "scored": 0, "r2": None, "duration_ms": 0}

    # Predecir y puntuar cada listing
    scored = 0
    for row in rows:
        listing_id = row["listing_id"]
        predicted = model.predict(row)
        if predicted is None or predicted == 0:
            continue
        actual = row["price"]
        score = (predicted - actual) / predicted
        listing = session.get(Listing, listing_id)
        if listing is not None:
            listing.bargain_score = round(score, 6)
            scored += 1

    # R²
    y = np.array([float(r["price"]) for r in rows])
    y_pred = np.array([model.predict(r) or 0.0 for r in rows])
    r2 = _r2_score(y, y_pred)

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("score_all: %d puntuados, R²=%.3f (%d ms)", scored, r2, duration_ms)
    return {"trained": True, "scored": scored, "r2": round(r2, 4), "duration_ms": duration_ms}
