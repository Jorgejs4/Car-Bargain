import pytest
from app.services.vision import (
    VisionUnavailableError,
    analyze_image_file,
    get_vision_analyzer,
)


def test_analyze_image_file_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        analyze_image_file(object(), "no/existe.jpg")


def test_get_vision_analyzer_raises_without_torch() -> None:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401

        pytest.skip("torch/open_clip instalados; el fallo sin dependencias no aplica")
    except ImportError:
        with pytest.raises(VisionUnavailableError):
            get_vision_analyzer()


def test_labels_are_fixed_and_unique() -> None:
    from app.services.vision import LABELS

    assert len(LABELS) == len(set(LABELS))
    assert "sin daños" in LABELS


def test_analyze_image_file_delegates(tmp_path) -> None:
    image_file = tmp_path / "a.jpg"
    image_file.write_bytes(b"x")
    calls: list[str] = []

    class _RecordingAnalyzer:
        def classify(self, path: str):
            calls.append(path)
            return "ok"

    result = analyze_image_file(_RecordingAnalyzer(), str(image_file))
    assert result == "ok"
    assert calls == [str(image_file)]
