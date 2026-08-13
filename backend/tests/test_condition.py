from scrapers.base.condition import extract_condition_signals


def test_condition_marks_explicit_fault_and_blocks_deal() -> None:
    result = extract_condition_signals(
        "Motor averiado, no arranca y sin papeles",
        lang="es",
        title="BMW 320d",
        description="Motor averiado, no arranca y sin papeles",
    )

    assert result["has_problem"] is True
    assert "has_engine_issue" in result["problem_types"]
    assert result["has_paper_issue"] is True
    assert result["deal_eligible"] is False
    assert result["text_status"] == "problem"


def test_condition_does_not_mark_negated_fault() -> None:
    result = extract_condition_signals(
        "Vehículo sin averías ni accidentes, documentación en regla",
        lang="es",
        title="Toyota Corolla",
        description="Vehículo sin averías ni accidentes, documentación en regla",
    )

    assert result["has_problem"] is False
    assert result["deal_eligible"] is True
    assert result["has_papers"] is True


def test_missing_description_is_unknown_not_clean() -> None:
    result = extract_condition_signals("BMW 320d 2020", lang="es", title="BMW 320d 2020")

    assert result["text_status"] == "clear"
    assert result["description_available"] is False
    assert result["deal_eligible"] is False


def test_condition_supports_european_languages() -> None:
    result = extract_condition_signals(
        "Moteur défectueux, sans papiers",
        lang="fr",
        title="Peugeot 308",
        description="Moteur défectueux, sans papiers",
    )

    assert result["has_problem"] is True
    assert result["deal_eligible"] is False
