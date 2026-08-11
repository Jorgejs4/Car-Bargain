"""Extracción de señales de estado/daños a partir de texto (título + descripción).

Produce `condition_signals` estructurados con `confidence` y `source`, respetando la
invariante de Data Quality: ausencia de palabras ≠ buen estado (bucket `unknown`).
"""

import re
from typing import Literal

SIGNAL_KEYS = (
    "accident_free",
    "has_accident",
    "has_cosmetic_damage",
    "has_rust",
    "has_repaint",
    "has_engine_issue",
)

# Lexicón: señal -> patrones por idioma (regex, case-insensitive).
# Los patrones positivos/negativos se ordenan para no confundir "unfallfrei" con "unfallwagen".
_LEXICON: dict[str, dict[str, list[str]]] = {
    "de": {
        "accident_free": [r"\bunfallfrei(?:heitsbescheinigung)?\b", r"\bunfallfreier\b", r"\bohne unfall\b"],
        "has_accident": [r"\bunfallwagen\b", r"\bunfallschaden\b", r"\bunfall beschädigt\b", r"\bmit unfall\b"],
        "has_cosmetic_damage": [r"\bkratzer\b", r"\bbeule(?:n)?\b", r"\bdelle(?:n)?\b", r"\bsteinschlag\b"],
        "has_rust": [r"\brost\b", r"\bkorrosion\b", r"\bverrostet\b"],
        "has_repaint": [r"\blackiert\b", r"\bneulackierung\b", r"\bneulackiert\b", r"\bfolierung\b"],
        "has_engine_issue": [r"\bmotorschaden\b", r"\bmotor defekt\b", r"\bmotor kaputt\b", r"\bgetriebeschaden\b"],
    },
    "es": {
        "accident_free": [r"\bsin accidentes?\b", r"\bsin golpes\b", r"\bnunca accidentado\b", r"\bsin siniestros?\b"],
        "has_accident": [r"\baccidentad[oa]\b", r"\bchocad[oa]\b", r"\bdado de baja\b", r"\bsiniestrad[oa]\b", r"\bcon accidentes?\b"],
        "has_cosmetic_damage": [r"\broces?\b", r"\babolladuras?\b", r"\brayad[oa]s?\b", r"\bgolpes?\b", r"\bmarcas de uso\b"],
        "has_rust": [r"\bóxido\b", r"\bherrumbre\b", r"\boxidad[oa]\b"],
        "has_repaint": [r"\brepintad[oa]\b", r"\brepinturas?\b", r"\bpolémico\b"],
        "has_engine_issue": [r"\bavería de motor\b", r"\bavería mecánica\b", r"\bmotor reparado\b", r"\breparación de motor\b"],
    },
}

_SUPPORTED_LANGS: set[str] = set(_LEXICON)


def _compile(lang: str) -> dict[str, list[re.Pattern]]:
    return {signal: [re.compile(p, re.IGNORECASE) for p in patterns] for signal, patterns in _LEXICON[lang].items()}


_COMPILED = {lang: _compile(lang) for lang in _LEXICON}


def _confidence_for(n_matches: int, total: int) -> float:
    if total == 0:
        return 0.0
    if total >= 3:
        return 0.9
    if total == 2:
        return 0.8
    return 0.7


def extract_condition_signals(
    text: str | None,
    *,
    lang: Literal["de", "es"] = "de",
    source: str = "description",
) -> dict:
    """Devuelve un dict JSONB-ready con las señales de estado detectadas.

    Si el texto es None o vacío, devuelve todas las señales en `None` (unknown).
    """
    empty: dict = {key: None for key in SIGNAL_KEYS}
    empty.update({"text_contradiction": False, "keywords_found": [], "source": source, "confidence": 0.0})
    if not text:
        return empty

    if lang not in _SUPPORTED_LANGS:
        raise ValueError(f"Idioma no soportado: {lang}")

    found: list[str] = []
    signals: dict[str, bool] = {}
    for signal, patterns in _COMPILED[lang].items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                signals[signal] = True
                found.append(match.group(0))
                break

    result: dict = {key: signals.get(key, False) for key in SIGNAL_KEYS}

    # Unfallfrei es una afirmación positiva; no debe contar como accidente.
    if result["accident_free"]:
        result["has_accident"] = False

    contradiction = bool(result["accident_free"] and any(result[k] for k in ("has_accident", "has_cosmetic_damage", "has_rust", "has_engine_issue")))

    result.update(
        {
            "text_contradiction": contradiction,
            "keywords_found": found,
            "source": source,
            "confidence": _confidence_for(len(signals), len(SIGNAL_KEYS)),
        }
    )
    return result
