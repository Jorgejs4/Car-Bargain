"""Motor de detección de daños visuales: CLIP zero-shot (open_clip + torch CPU).

No es el modelo principal de valoración (invariante del dominio): sus salidas
alimentan `photo_analyses`, `condition_signals`/`photo_signals` y el Risk Score.

Las dependencias (`torch`, `open_clip_torch`, `pillow`) se importan de forma
perezosa para no engordar el entorno base; si no están instaladas, la tarea
`images.analyze` degrada con `cv_unavailable` sin romper el pipeline.
"""

import logging
from functools import lru_cache
from pathlib import Path

from app.schemas.photo_analysis import PhotoAnalysisResult

logger = logging.getLogger(__name__)

# Etiquetas de daño por foto (orden fijo = orden de los prompts).
LABELS = ["sin daños", "roces", "abolladura", "óxido", "cristal roto", "repintado"]

_PROMPTS = [
    "a photo of a car in perfect condition, no damage, clean bodywork",
    "a photo of a car with scratches and light scuffs on the paint",
    "a photo of a car with a dented or deformed body panel",
    "a photo of a car with rust or corrosion on the body",
    "a photo of a car with a broken, cracked or missing window",
    "a photo of a car with freshly repainted bodywork, color mismatch",
]


class VisionUnavailableError(RuntimeError):
    """El motor CV no está disponible (torch/open_clip no instalados o error de carga)."""


class VisionAnalyzer:
    """Clasificador zero-shot por fotografía usando CLIP."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        pretrained: str | None = None,
        device: str | None = None,
    ) -> None:
        try:
            import open_clip  # type: ignore[import-not-found]
            import torch  # type: ignore[import-not-found]
        except ImportError as exc:
            raise VisionUnavailableError(
                "torch/open_clip no están instalados (pip install -r requirements-cv.txt)"
            ) from exc

        from app.core.config import settings

        self._model_name = model_name or settings.cv_model_name
        self._pretrained = pretrained or settings.cv_pretrained
        self.model_version = f"open_clip/{self._model_name}:{self._pretrained}"

        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            self._model_name, pretrained=self._pretrained
        )
        self._tokenizer = open_clip.get_tokenizer(self._model_name)
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = self._model.to(self._device).eval()
        logger.info("VisionAnalyzer listo: %s en %s", self.model_version, self._device)

    def classify(self, image_path: str) -> PhotoAnalysisResult:
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._preprocess(image).unsqueeze(0).to(self._device)
        texts = self._tokenizer(_PROMPTS).to(self._device)

        with torch.no_grad():
            image_features = self._model.encode_image(inputs)
            text_features = self._model.encode_text(texts)
            logits = (image_features @ text_features.T).softmax(dim=-1)[0]

        top = int(logits.argmax(dim=-1))
        return PhotoAnalysisResult(
            label=LABELS[top],
            probability=float(logits[top]),
            model_version=self.model_version,
        )


@lru_cache(maxsize=1)
def _cached_analyzer() -> VisionAnalyzer:
    return VisionAnalyzer()


def get_vision_analyzer() -> VisionAnalyzer:
    """Devuelve el analyzer cacheado o lanza `VisionUnavailableError` si no puede cargarse."""
    try:
        return _cached_analyzer()
    except (VisionUnavailableError, ImportError) as exc:
        raise VisionUnavailableError(str(exc)) from exc


def analyze_image_file(analyzer: VisionAnalyzer, image_path: str) -> PhotoAnalysisResult:
    """Clasifica un archivo de imagen existente; falla limpio si no existe."""
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")
    return analyzer.classify(image_path)
