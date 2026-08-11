"""Vehicle matching (Fase 5): resuelve `vehicle_id` de un listing a un vehículo.

Estrategias, de más a menos estricta:
1. `exact`    — marca, modelo, generación, combustible, cambio y variante coinciden
   (normalizados) + año (±1) + potencia (±1 kW). Mismo vehículo inequívoco.
2. `normalized` — igual pero la variante difiere en texto y aun así está por encima
   del umbral de similaridad (ej. `M Sport` vs `M Sportpaket`): misma plataforma.
3. `fuzzy`    — marca y modelo con similaridad de tokens ≥ umbral, año/potencia
   tolerantes y combustible/cambio compatibles.
4. `created`  — no hay candidato compatible: se crea un vehículo nuevo.

La ingesta conserva la traza raw → normalized + confidence + source en
`vehicle_matches` (append-only por listing).
"""

import logging
from dataclasses import dataclass

from rapidfuzz import fuzz
from scrapers.base.models import NormalizedListing
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Vehicle
from app.services.normalization import normalize_identity

logger = logging.getLogger(__name__)

_YEAR_TOLERANCE = 1
_POWER_TOLERANCE_KW = 1.0


@dataclass
class MatchResult:
    vehicle: Vehicle
    strategy: str  # exact | normalized | fuzzy | created
    confidence: float
    normalized_value: dict[str, str | None]


def _identity(nl: NormalizedListing) -> dict[str, str | None]:
    return normalize_identity(
        brand=nl.brand,
        model=nl.model,
        generation=nl.generation,
        variant=nl.variant,
        fuel=nl.fuel,
        transmission=nl.transmission,
    )


def _single(field: str, value: str | None) -> str | None:
    return normalize_identity(**{field: value})[field]


def _confidence_for(strategy: str, fuzzy_score: float | None = None) -> float:
    if strategy == "exact":
        return 1.0
    if strategy == "normalized":
        return 0.95
    if strategy == "fuzzy":
        return max(settings.match_fuzzy_threshold, (fuzzy_score or 0) / 100.0)
    return 1.0  # created: no hay certeza previa, se asume identidad nueva


def _core_matches(
    candidate: Vehicle, ident: dict, nl: NormalizedListing, *, require_model: bool = True
) -> bool:
    """Campos núcleo: modelo, generación, combustible, cambio + año y potencia tolerantes."""
    for field in ("model", "generation", "fuel", "transmission"):
        cand_value = getattr(candidate, field)
        target = ident.get(field)
        if target is None:
            continue
        if cand_value is not None and _single(field, cand_value) != target:
            if field == "model" and not require_model:
                continue
            return False
    if candidate.year is not None and nl.year is not None and abs(candidate.year - nl.year) > _YEAR_TOLERANCE:
        return False
    return not (
        candidate.power_kw is not None
        and nl.power_kw is not None
        and abs(float(candidate.power_kw) - nl.power_kw) > _POWER_TOLERANCE_KW
    )


def _variant_compat(candidate: Vehicle, ident: dict) -> str:
    """Compatibilidad de variante: identical | partial | fuzzy_ok | mismatch."""
    cand_variant = _single("variant", candidate.variant)
    target_variant = ident.get("variant")
    if cand_variant == target_variant:
        return "identical"
    if not cand_variant or not target_variant:
        return "partial"  # un lado sin variante: no confirmable, no contradictorio
    score = float(fuzz.token_sort_ratio(cand_variant, target_variant))
    if score >= settings.match_fuzzy_threshold * 100.0:
        return "fuzzy_ok"
    return "mismatch"


def _best_candidate(
    session: Session, ident: dict, nl: NormalizedListing
) -> tuple[str, float, Vehicle | None]:
    """Devuelve `(strategy, confidence, vehicle)` o `("created", 1.0, None)`."""
    brand = ident.get("brand")
    if not brand:
        return "created", 1.0, None

    candidates = session.scalars(select(Vehicle).where(Vehicle.brand.is_not(None))).all()
    brand_matched = [c for c in candidates if _single("brand", c.brand) == brand]

    # 1. exact: núcleo + variante idéntica tras normalizar
    for candidate in brand_matched:
        if _core_matches(candidate, ident, nl) and _variant_compat(candidate, ident) == "identical":
            return "exact", _confidence_for("exact"), candidate

    # 2. normalized: núcleo + variante parcial o suficientemente similar
    for candidate in brand_matched:
        if not _core_matches(candidate, ident, nl):
            continue
        if _variant_compat(candidate, ident) in ("partial", "fuzzy_ok"):
            return "normalized", _confidence_for("normalized"), candidate

    # 3. fuzzy: marca igual + modelo similar + resto del núcleo tolerante (año/potencia)
    best: tuple[float, Vehicle | None] = (0.0, None)
    for candidate in brand_matched:
        if not _core_matches(candidate, ident, nl, require_model=False):
            continue
        cand_model = _single("model", candidate.model) or ""
        target_model = ident.get("model") or ""
        if not cand_model or not target_model:
            continue
        score = float(fuzz.token_sort_ratio(cand_model, target_model))
        if score > best[0]:
            best = (score, candidate)
    fuzzy_score, candidate = best
    if candidate is not None and fuzzy_score / 100.0 >= settings.match_fuzzy_threshold:
        return "fuzzy", _confidence_for("fuzzy", fuzzy_score), candidate
    return "created", 1.0, None


def match_vehicle(session: Session, nl: NormalizedListing) -> MatchResult:
    """Asigna (o crea) el vehículo del anuncio y devuelve el resultado del match.

    No persiste `vehicle_matches`; la ingesta lo hace con el `listing_id` real.
    El commit lo decide el llamador.
    """
    ident = _identity(nl)
    strategy, confidence, candidate = _best_candidate(session, ident, nl)

    if candidate is None:
        candidate = Vehicle(
            brand=nl.brand,
            model=nl.model,
            generation=nl.generation,
            variant=nl.variant,
            fuel=nl.fuel,
            transmission=nl.transmission,
            year=nl.year,
            power_kw=nl.power_kw,
            co2_g_km=nl.co2_g_km,
        )
        session.add(candidate)
        session.flush()

    return MatchResult(
        vehicle=candidate,
        strategy=strategy,
        confidence=confidence,
        normalized_value=ident,
    )
