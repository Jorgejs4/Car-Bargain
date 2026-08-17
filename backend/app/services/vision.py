"""Motor de detección de daños visuales: CLIP zero-shot (open_clip + torch CPU).

No es el modelo principal de valoración (invariante del dominio): sus salidas
alimentan `photo_analyses`, `condition_signals`/`photo_signals` y el Risk Score.

Las dependencias (`torch`, `open_clip_torch`, `pillow`) se importan de forma
perezosa para no engordar el entorno base; si no están instaladas, la tarea
`images.analyze` degrada con `cv_unavailable` sin romper el pipeline.
"""

import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas.photo_analysis import PhotoAnalysisResult

logger = logging.getLogger(__name__)

# Etiquetas de daño por foto (orden fijo = orden de los prompts).
LABELS = ["sin daños", "roces", "abolladura", "óxido", "cristal roto", "repintado"]

_PROMPTS = [
    "a photo of a used car with clean undamaged bodywork, no dents no scratches no rust",
    "a photo of a car with clearly visible scratches, scuffs or key marks on the paint",
    "a photo of a car with a large visible dent, bent or deformed body panel",
    "a photo of a car with noticeable rust spots, bubbling paint or corrosion on metal",
    "a photo of a car with shattered, cracked or completely broken window glass",
    "a photo of a car with obvious paint mismatch, different color panel or fresh repaint overspray",
]

# Clasificación de escena. Rueda/guardabarro se separa para poder buscar daños
# pequeños en una zona que suele ser especialmente relevante.
_SCENE_LABELS = ["exterior", "interior", "motor", "rueda/guardabarro", "documento", "otro"]

_SCENE_PROMPTS = [
    "a photo of the outside of a car showing the body, doors, hood, trunk, roof or side profile",
    "a photo inside a car showing dashboard, seats, steering wheel, pedals, gear lever, screens or door panels",
    "a photo of a car engine bay, open hood showing motor, belts, battery or mechanical components",
    "a close-up photo of a car wheel, tire, wheel arch or fender/guardabarro",
    "a photo of a document, rating badge, dealership sign, text, logo, stamp, certificate or screenshot",
    "a photo of a car wheel, tire, headlight, taillight, trunk interior, fuel cap or other car detail",
]

_SOLD_WORDS = {"sold", "vendido", "verkauft", "vendu", "venduto", "verkocht", "solgt", "vândut", "sprzedany", "sprzedane"}


class VisionUnavailableError(RuntimeError):
    """El motor CV no está disponible (torch/open_clip no instalados o error de carga)."""


def detect_sold_text(image_path: str) -> tuple[str, float] | None:
    """Busca una marca de vendido mediante OCR en la primera imagen."""
    try:
        import pytesseract  # type: ignore[import-not-found]
        from PIL import Image, ImageEnhance, ImageOps
        tesseract_candidates = (
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        )
        for candidate in tesseract_candidates:
            if candidate.exists():
                pytesseract.pytesseract.tesseract_cmd = str(candidate)
                break
        tessdata_dir = Path(__file__).resolve().parents[3] / "tessdata"
        if (tessdata_dir / "eng.traineddata").exists():
            pytesseract_config = f'--tessdata-dir "{tessdata_dir}"'
        else:
            pytesseract_config = ""
        image = Image.open(image_path).convert("RGB")
        image = ImageOps.grayscale(image)
        image = ImageEnhance.Contrast(image.resize((image.width * 2, image.height * 2))).enhance(1.5)
        try:
            data = pytesseract.image_to_data(
                image,
                lang="eng+spa+deu+fra+ita+nld",
                config=pytesseract_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:  # noqa: BLE001
            data = pytesseract.image_to_data(
                image, lang="eng", config=pytesseract_config, output_type=pytesseract.Output.DICT
            )
    except Exception as exc:  # noqa: BLE001
        logger.info("OCR no disponible: %s", exc)
        return None

    matches: list[tuple[str, float]] = []
    for raw, confidence in zip(data.get("text", []), data.get("conf", [])):
        normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().lower()
        normalized = re.sub(r"[^a-z]+", "", normalized)
        if normalized in _SOLD_WORDS:
            try:
                score = float(confidence) / 100
            except (TypeError, ValueError):
                score = 0.0
            if score >= 0.70:
                matches.append((normalized, score))
    return max(matches, key=lambda item: item[1]) if matches else None


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

    def _classify_image(self, image, prompts: list[str]) -> tuple[int, float]:
        import torch

        inputs = self._preprocess(image).unsqueeze(0).to(self._device)
        texts = self._tokenizer(prompts).to(self._device)

        with torch.no_grad():
            image_features = self._model.encode_image(inputs)
            text_features = self._model.encode_text(texts)
            logits = (image_features @ text_features.T).softmax(dim=-1)[0]

        top = int(logits.argmax(dim=-1))
        return top, float(logits[top])

    def classify(self, image_path: str) -> PhotoAnalysisResult:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        # CLIP recibe 224x224, pero analizamos varios recortes solapados de la
        # imagen original para no perder daños pequeños al reducirla.
        width, height = image.size
        crop_w, crop_h = max(width // 2, 1), max(height // 2, 1)
        boxes = [(0, 0, width, height)]
        for y in (0, max(height - crop_h, 0)):
            for x in (0, max(width - crop_w, 0)):
                box = (x, y, min(x + crop_w, width), min(y + crop_h, height))
                if box not in boxes:
                    boxes.append(box)

        scores = [0.0] * len(LABELS)
        for box in boxes:
            top, probability = self._classify_image(image.crop(box), _PROMPTS)
            scores[top] = max(scores[top], probability)
        top = max(range(len(scores)), key=scores.__getitem__)
        return PhotoAnalysisResult(
            label=LABELS[top],
            probability=scores[top],
            model_version=self.model_version,
        )

    def classify_scene(self, image_path: str) -> tuple[str, float]:
        """Clasifica la escena: exterior, interior, motor o otro.

        Las fotos de exterior y rueda/guardabarro pasan al detector de daños.
        """
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        top, probability = self._classify_image(image, _SCENE_PROMPTS)
        return _SCENE_LABELS[top], probability


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
