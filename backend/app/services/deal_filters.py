"""Reglas compartidas para decidir si un anuncio puede ser una ganga."""


def is_clean_deal(
    text_signals: dict | None,
    photo_signals: dict | None,
    needs_review: bool,
) -> bool:
    """True solo con texto analizado, sin incidencias y sin daño visual."""
    return bool(
        not needs_review
        and text_signals
        and text_signals.get("deal_eligible") is True
        and not (photo_signals or {}).get("has_visible_damage", False)
    )
