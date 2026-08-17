"""Extracción local y gratuita de señales de estado desde texto.

El analizador es deliberadamente conservador y no depende de una API externa:
detecta expresiones explícitas en varios idiomas y separa ``problem``,
``clear`` y ``unknown``. La ausencia de una descripción nunca se interpreta
como buen estado.
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
    "has_mechanical_issue",
    "has_gearbox_issue",
    "has_paper_issue",
    "has_fire_or_flood_damage",
    "not_running",
    "export_or_parts",
)

_ISSUE_KEYS = (
    "has_accident",
    "has_cosmetic_damage",
    "has_rust",
    "has_repaint",
    "has_engine_issue",
    "has_mechanical_issue",
    "has_gearbox_issue",
    "has_paper_issue",
    "has_fire_or_flood_damage",
    "not_running",
    "export_or_parts",
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
        "has_mechanical_issue": [r"\bmechanischer schaden\b", r"\breparaturbedürftig\b", r"\breparatur nötig\b", r"\bdefekt\b"],
        "has_gearbox_issue": [r"\bgetriebe defekt\b", r"\bgetriebe kaputt\b", r"\bkupplung defekt\b"],
        "has_paper_issue": [r"\bohne papiere\b", r"\bkeine papiere\b", r"\bohne fahrzeugbrief\b", r"\bohne tüv\b"],
        "has_fire_or_flood_damage": [r"\bbrandschaden\b", r"\bfeuerschaden\b", r"\bwasserschaden\b", r"\bflutschaden\b", r"\bhagelschaden\b"],
        "not_running": [r"\bnicht fahrbereit\b", r"\bnicht fahrfähig\b", r"\bnicht fahrend\b"],
        "export_or_parts": [r"\bals ersatzteil\b", r"\bteileträger\b", r"\bnur export\b", r"\bexportfahrzeug\b", r"\bbastlerfahrzeug\b"],
    },
    "es": {
        "accident_free": [r"\bsin accidentes?\b", r"\bsin golpes\b", r"\bnunca accidentado\b", r"\bsin siniestros?\b"],
        "has_accident": [r"\baccidentad[oa]\b", r"\bchocad[oa]\b", r"\bdado de baja\b", r"\bsiniestrad[oa]\b", r"\bcon accidentes?\b"],
        "has_cosmetic_damage": [r"\broces?\b", r"\babolladuras?\b", r"\brayad[oa]s?\b", r"\bgolpes?\b", r"\bmarcas de uso\b", r"\bdaños? de chapa\b"],
        "has_rust": [r"\bóxido\b", r"\bherrumbre\b", r"\boxidad[oa]\b"],
        "has_repaint": [r"\brepintad[oa]\b", r"\brepinturas?\b", r"\bpolémico\b"],
        "has_engine_issue": [r"\baver[ií]a de motor\b", r"\bmotor averiad[oa]\b", r"\bmotor defectuoso\b", r"\bmotor roto\b", r"\bmotor reparado\b", r"\breparaci[oó]n de motor\b", r"\bcheck engine\b"],
        "has_mechanical_issue": [r"\baver[ií]a mec[aá]nica\b", r"\bproblema mec[aá]nico\b", r"\bdefecto mec[aá]nico\b", r"\bpara reparar\b", r"\bnecesita reparaci[oó]n\b"],
        "has_gearbox_issue": [r"\bcaja de cambios? averiad[ao]\b", r"\bcaja de cambios? rota\b", r"\bembrague averiad[oa]\b", r"\bembrague gastado\b", r"\bcambio defectuoso\b"],
        "has_paper_issue": [r"\bsin papeles?\b", r"\bsin documentaci[oó]n\b", r"\bsin permiso de circulaci[oó]n\b", r"\bsin itv\b", r"\bno tiene papeles?\b"],
        "has_fire_or_flood_damage": [r"\bincendiad[oa]\b", r"\bdaño por agua\b", r"\binundad[oa]\b", r"\bdaño por granizo\b"],
        "not_running": [r"\bno arranca\b", r"\bno funciona\b", r"\bno circula\b", r"\bno es conducible\b"],
        "export_or_parts": [r"\bpara piezas?\b", r"\bdespiece\b", r"\bsolo para exportaci[oó]n\b", r"\bveh[ií]culo de exportaci[oó]n\b"],
    },
    "fr": {
        "accident_free": [r"\bsans accident\b", r"\bjamais accident[ée]\b"],
        "has_accident": [r"\baccident[ée]\b", r"\baccident[eé]e\b", r"\bv[eé]hicule accident[ée]\b"],
        "has_cosmetic_damage": [r"\brayures?\b", r"\bbosses?\b", r"\bchocs?\b", r"\bcarrosserie endommag[ée]e\b"],
        "has_rust": [r"\brouille\b", r"\bcorrosion\b"],
        "has_repaint": [r"\brepeint\b", r"\brepeinture\b", r"\bpeinture refaite\b"],
        "has_engine_issue": [r"\bmoteur hs\b", r"\bpanne moteur\b", r"\bmoteur d[ée]fectueux\b", r"\bmoteur cass[ée]\b"],
        "has_mechanical_issue": [r"\bpanne m[ée]canique\b", r"\bprobl[eè]me m[ée]canique\b", r"\b[àa] r[ée]parer\b"],
        "has_gearbox_issue": [r"\bbo[iî]te de vitesses? hs\b", r"\bembrayage hs\b"],
        "has_paper_issue": [r"\bsans papiers?\b", r"\bsans carte grise\b", r"\bsans contr[oô]le technique\b"],
        "has_fire_or_flood_damage": [r"\bincendi[ée]\b", r"\bd[eé]g[aâ]t des eaux\b", r"\binond[ée]\b", r"\bgr[eê]le\b"],
        "not_running": [r"\bnon roulant\b", r"\bne d[eé]marre pas\b", r"\bne roule pas\b"],
        "export_or_parts": [r"\bpour pi[eè]ces\b", r"\bpour export\b", r"\bvendu pour pi[eè]ces\b"],
    },
    "it": {
        "accident_free": [r"\bmai incidentata\b", r"\bsenza incidenti\b"],
        "has_accident": [r"\bincidentata\b", r"\bdanneggiata\b", r"\bveicolo incidentato\b"],
        "has_cosmetic_damage": [r"\bgraffi\b", r"\bammaccature?\b", r"\bbotte\b", r"\bdanni alla carrozzeria\b"],
        "has_rust": [r"\bruggine\b", r"\bcorrosione\b"],
        "has_repaint": [r"\briverniciata\b", r"\briverniciatura\b", r"\bverniciata\b"],
        "has_engine_issue": [r"\bmotore rotto\b", r"\bmotore guasto\b", r"\bproblema al motore\b"],
        "has_mechanical_issue": [r"\bguasto meccanico\b", r"\bproblema meccanico\b", r"\bda riparare\b"],
        "has_gearbox_issue": [r"\bcambio rotto\b", r"\bfrizione guasta\b"],
        "has_paper_issue": [r"\bsenza documenti\b", r"\bsenza libretto\b", r"\bsenza revisione\b"],
        "has_fire_or_flood_damage": [r"\bdanni da incendio\b", r"\bdanni d'acqua\b", r"\balluvionata\b", r"\bgrandine\b"],
        "not_running": [r"\bnon marciante\b", r"\bnon parte\b", r"\bnon funzionante\b"],
        "export_or_parts": [r"\bper ricambi\b", r"\bsolo export\b", r"\bda demolizione\b"],
    },
    "nl": {
        "accident_free": [r"\bongevalvrij\b", r"\bschadevrij\b"],
        "has_accident": [r"\bauto met schade\b", r"\bongevalauto\b", r"\bongevalschade\b", r"\bschadeauto\b"],
        "has_cosmetic_damage": [r"\bkrassen\b", r"\bdeuken\b", r"\bdeuk(en)?\b", r"\bcarrosserieschade\b"],
        "has_rust": [r"\broest\b", r"\bcorrosie\b"],
        "has_repaint": [r"\bovergespoten\b", r"\bgespoten\b", r"\bovergespoten delen\b"],
        "has_engine_issue": [r"\bmotor defect\b", r"\bmotorschade\b", r"\bmotor kapot\b"],
        "has_mechanical_issue": [r"\bmechanisch defect\b", r"\breparatie nodig\b", r"\bte repareren\b"],
        "has_gearbox_issue": [r"\bversnellingsbak defect\b", r"\bkoppeling defect\b"],
        "has_paper_issue": [r"\bzonder papieren\b", r"\bgeen kentekenbewijs\b", r"\bzonder apk\b"],
        "has_fire_or_flood_damage": [r"\bbrandschade\b", r"\bwaterschade\b", r"\boverstromingsschade\b", r"\bhagelschade\b"],
        "not_running": [r"\bniet rijklaar\b", r"\bstart niet\b", r"\bloopt niet\b"],
        "export_or_parts": [r"\bvoor onderdelen\b", r"\balleen export\b", r"\bsloperij\b"],
    },
    "en": {
        "accident_free": [r"\baccident[- ]free\b", r"\bnever crashed\b"],
        "has_accident": [r"\baccident damaged\b", r"\bcrashed\b", r"\baccident car\b", r"\bwrite[- ]off\b"],
        "has_cosmetic_damage": [r"\bscratches?\b", r"\bdents?\b", r"\bbody damage\b", r"\bcosmetic damage\b"],
        "has_rust": [r"\brust\b", r"\bcorrosion\b"],
        "has_repaint": [r"\brepainted\b", r"\bresprayed\b", r"\brepaint\b"],
        "has_engine_issue": [r"\bengine failure\b", r"\bengine damage\b", r"\bengine faulty\b", r"\bblown engine\b"],
        "has_mechanical_issue": [r"\bmechanical fault\b", r"\bmechanical issue\b", r"\bneeds repair\b"],
        "has_gearbox_issue": [r"\bgearbox fault\b", r"\btransmission fault\b", r"\bclutch fault\b"],
        "has_paper_issue": [r"\bno papers\b", r"\bno documents\b", r"\bwithout registration\b", r"\bno mot\b"],
        "has_fire_or_flood_damage": [r"\bfire damaged\b", r"\bflood damaged\b", r"\bwater damaged\b", r"\bhail damage\b"],
        "not_running": [r"\bnon[- ]runner\b", r"\bdoes not start\b", r"\bnot running\b"],
        "export_or_parts": [r"\bfor parts\b", r"\bparts only\b", r"\bexport only\b"],
    },
}

_SUPPORTED_LANGS: set[str] = set(_LEXICON)

_LANG_BY_COUNTRY = {
    "DE": "de",
    "AT": "de",
    "CH": "de",
    "ES": "es",
    "FR": "fr",
    "LU": "fr",
    "IT": "it",
    "NL": "nl",
    "BE": "nl",
}


def language_for_country(country: str | None) -> str:
    """Devuelve el idioma de análisis más probable para un país ISO."""
    return _LANG_BY_COUNTRY.get((country or "").upper(), "en")


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


def _is_negated(text: str, start: int) -> bool:
    """Evita marcar ``sin averías``/``ohne Schaden`` como una avería."""
    prefix = text[max(0, start - 48):start].lower()
    return bool(
        re.search(
            r"(?:\bsin\b|\bno\b|\bohne\b|\bsans\b|\bsenza\b|\bzonder\b|\bwithout\b)"
            r"(?:\s+[\wáéíóúüäöß'-]+){0,3}\s*$",
            prefix,
        )
    )


def extract_condition_signals(
    text: str | None,
    *,
    lang: Literal["de", "es", "fr", "it", "nl", "en"] = "de",
    source: str = "description",
    title: str | None = None,
    description: str | None = None,
) -> dict:
    """Devuelve un dict JSONB-ready con las señales de estado detectadas.

    Si el texto es None o vacío, devuelve todas las señales en `None` (unknown).
    """
    text_available = bool(text and text.strip())
    description_available = bool(description and description.strip())
    empty: dict = {key: False for key in SIGNAL_KEYS}
    empty.update(
        {
            "text_contradiction": False,
            "keywords_found": [],
            "problem_types": [],
            "highlights": [],
            "has_problem": False,
            "has_papers": None,
            "has_warranty": None,
            "text_status": "unknown",
            "text_available": text_available,
            "description_available": description_available,
            "deal_eligible": False,
            "source": source,
            "confidence": 0.0,
            "analyzer_version": "lexicon-v2",
        }
    )
    if not text:
        return empty

    if lang not in _SUPPORTED_LANGS:
        raise ValueError(f"Idioma no soportado: {lang}")

    found: list[str] = []
    signals: dict[str, bool] = {}
    for signal, patterns in _COMPILED[lang].items():
        for pattern in patterns:
            match = pattern.search(text)
            if match and (
                signal in ("accident_free", "has_paper_issue", "not_running", "export_or_parts")
                or not _is_negated(text, match.start())
            ):
                signals[signal] = True
                found.append(match.group(0))
                break

    result: dict = {**empty, **{key: signals.get(key, False) for key in SIGNAL_KEYS}}

    # Unfallfrei es una afirmación positiva; no debe contar como accidente.
    if result["accident_free"]:
        result["has_accident"] = False

    contradiction = bool(result["accident_free"] and any(result[k] for k in _ISSUE_KEYS))
    # Los defectos de carrocería se conservan como señal informativa, pero no
    # son una avería mecánica ni deben bloquear una ganga.
    problem_types = [
        key for key in _ISSUE_KEYS
        if result[key] and key not in {"has_cosmetic_damage", "has_repaint"}
    ]
    papers_ok_patterns = re.compile(
        r"(?:papeles|documentaci[oó]n)\s+en\s+regla|"
        r"papiers\s+en\s+r[eè]gle|documenti\s+in\s+regola|"
        r"documenten\s+in\s+orde|documents?\s+in\s+order|"
        r"papers?\s+in\s+order|vollst[aä]ndige papiere|alle papiere",
        re.IGNORECASE,
    )
    has_papers = True if papers_ok_patterns.search(text) else None
    if result["has_paper_issue"]:
        has_papers = False
    has_warranty = None
    warranty_patterns = re.compile(
        r"\b(?:garant[ií]a|garantie|garanzia|warranty)\b", re.IGNORECASE
    )
    no_warranty_patterns = re.compile(
        r"(?:\bsin\b|\bohne\b|\bsans\b|\bsenza\b|\bzonder\b|\bwithout\b)\s+"
        r"(?:garant[ií]a|garantie|garanzia|warranty)",
        re.IGNORECASE,
    )
    if warranty_patterns.search(text) and not no_warranty_patterns.search(text):
        has_warranty = True
    elif no_warranty_patterns.search(text):
        has_warranty = False

    text_status = "problem" if problem_types else "clear"
    highlights = problem_types.copy()
    if has_papers is True:
        highlights.append("papeles/documentación en regla")
    if has_warranty is True:
        highlights.append("garantía")
    if has_warranty is False:
        highlights.append("sin garantía indicada")
    if has_warranty is False:
        highlights.append("sin garantía indicada")

    result.update(
        {
            "text_contradiction": contradiction,
            "keywords_found": found,
            "problem_types": problem_types,
            "highlights": highlights,
            "has_problem": bool(problem_types),
            "has_papers": has_papers,
            "has_warranty": has_warranty,
            "text_status": text_status,
            "deal_eligible": bool(description_available and not problem_types and not result["has_paper_issue"]),
            "source": source,
            "confidence": _confidence_for(len(signals), len(SIGNAL_KEYS)),
        }
    )
    return result
