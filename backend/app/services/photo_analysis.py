"""Agregación del análisis visual por anuncio y evaluación de riesgo/contradicción (Fase 3).

Las señales agregadas se guardan en `listings.photo_signals`:
`photo_damage_prob`, `has_visible_damage`, `damage_types`, `analyzed_images`.

El Risk Score y `needs_review` combinan las señales de foto y de texto; la
contradicción texto/foto (ej. "unfallfrei" + foto dañada) sube el riesgo y
marca revisión manual. Nunca asumimos buen estado sin evidencia (`unknown`).
"""

from app.core.config import settings
from app.schemas.photo_analysis import PhotoAnalysisResult

_NO_DAMAGE_LABEL = "sin daños"


def aggregate_photo_signals(analyses: list[PhotoAnalysisResult]) -> dict | None:
    """Agrega los resultados por foto en un único dict para `listings.photo_signals`."""
    if not analyses:
        return None

    damaged = [
        a for a in analyses if a.label != _NO_DAMAGE_LABEL and a.probability >= settings.damage_prob_min
    ]
    has_visible_damage = bool(damaged)
    damage_types = sorted({a.label for a in damaged})
    damaged_probs = [a.probability for a in damaged]
    photo_damage_prob = max(damaged_probs) if damaged_probs else 0.0

    return {
        "photo_damage_prob": round(photo_damage_prob, 4),
        "has_visible_damage": has_visible_damage,
        "damage_types": damage_types,
        "analyzed_images": len(analyses),
    }


def evaluate_damage_risk(photo_signals: dict | None, text_signals: dict | None) -> tuple[float, bool]:
    """Devuelve `(risk_score 0..1, needs_review)` a partir de señales de foto y texto."""
    risk = 0.0
    needs_review = False

    if photo_signals and photo_signals.get("has_visible_damage"):
        risk += 0.5
        risk += 0.2 * len(photo_signals.get("damage_types") or [])

    if text_signals:
        for key in ("has_accident", "has_engine_issue", "has_rust"):
            if text_signals.get(key):
                risk += 0.2

        contradiction = bool(
            (text_signals.get("accident_free") and photo_signals and photo_signals.get("has_visible_damage"))
            or text_signals.get("text_contradiction")
        )
        if contradiction:
            needs_review = True
            risk += settings.contradiction_tolerance

    return min(round(risk, 3), 1.0), needs_review
