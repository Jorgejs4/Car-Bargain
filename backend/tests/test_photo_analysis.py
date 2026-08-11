from app.core.config import settings
from app.schemas.photo_analysis import PhotoAnalysisResult
from app.services.photo_analysis import aggregate_photo_signals, evaluate_damage_risk


def _result(label: str, probability: float) -> PhotoAnalysisResult:
    return PhotoAnalysisResult(label=label, probability=probability, model_version="test/1.0")


def test_aggregate_none_without_analyses() -> None:
    assert aggregate_photo_signals([]) is None


def test_aggregate_no_damage_detected() -> None:
    signals = aggregate_photo_signals([_result("sin daños", 0.95), _result("sin daños", 0.88)])

    assert signals is not None
    assert signals["has_visible_damage"] is False
    assert signals["damage_types"] == []
    assert signals["photo_damage_prob"] == 0.0
    assert signals["analyzed_images"] == 2


def test_aggregate_with_damage() -> None:
    signals = aggregate_photo_signals(
        [_result("sin daños", 0.9), _result("abolladura", 0.8), _result("óxido", 0.75)]
    )

    assert signals["has_visible_damage"] is True
    assert signals["damage_types"] == ["abolladura", "óxido"]
    assert signals["photo_damage_prob"] == 0.8
    assert signals["analyzed_images"] == 3


def test_aggregate_respects_damage_prob_min(monkeypatch) -> None:
    monkeypatch.setattr(settings, "damage_prob_min", 0.5)
    signals = aggregate_photo_signals([_result("roces", 0.3)])

    assert signals["has_visible_damage"] is False
    assert signals["damage_types"] == []


def test_risk_zero_without_evidence() -> None:
    risk, needs_review = evaluate_damage_risk(None, None)
    assert risk == 0.0
    assert needs_review is False


def test_risk_from_photo_damage() -> None:
    signals = aggregate_photo_signals([_result("abolladura", 0.8)])
    risk, needs_review = evaluate_damage_risk(signals, None)

    assert risk == 0.7  # 0.5 base + 0.2 por tipo de daño
    assert needs_review is False


def test_risk_from_text_damage() -> None:
    risk, _ = evaluate_damage_risk(
        None,
        {"has_accident": True, "has_rust": True, "accident_free": False, "text_contradiction": False},
    )
    assert risk == 0.4


def test_contradiction_photo_damages_and_text_says_clean(monkeypatch) -> None:
    monkeypatch.setattr(settings, "contradiction_tolerance", 0.3)
    photo = aggregate_photo_signals([_result("óxido", 0.9)])
    text = {"accident_free": True, "has_accident": False, "text_contradiction": False}

    risk, needs_review = evaluate_damage_risk(photo, text)

    assert needs_review is True
    assert risk == 1.0  # 0.5 + 0.2 + 0.3 (tope 1.0)


def test_text_contradiction_marks_review(monkeypatch) -> None:
    monkeypatch.setattr(settings, "contradiction_tolerance", 0.3)
    text = {
        "accident_free": True,
        "has_accident": True,
        "text_contradiction": True,
        "has_rust": False,
        "has_engine_issue": False,
    }

    risk, needs_review = evaluate_damage_risk(None, text)

    assert needs_review is True
    assert risk == 0.5  # 0.2 has_accident + 0.3 tolerancia
