"""Descarga y localización local de las imágenes de un anuncio.

Compartida por las tareas `images.download` (archivo raw) e `images.analyze`
(análisis CV). Es idempotente: las imágenes ya descargadas se reutilizan.
"""

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from scrapers.mobile_de.scraper import MobileDeScraper

from app.services import raw_store
from app.services.raw_store import save_image, save_manifest

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp", "gif", "avif"}


def _images_dir(source: str, source_listing_id: str) -> Path:
    return raw_store._DEFAULT_ROOT / source / "images" / source_listing_id


def _manifest_path(source: str, source_listing_id: str) -> Path:
    return _images_dir(source, source_listing_id) / "manifest.json"


def _load_manifest(source: str, source_listing_id: str) -> dict[str, dict]:
    """Devuelve {source_url: record} desde el manifest local, o {} si no existe."""
    path = _manifest_path(source, source_listing_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {img["source_url"]: img for img in data.get("images", [])}
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("manifest corrupto: %s", path)
        return {}


def _guess_extension(url: str, response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower().split("/")[-1].split(";")[0]
    if content_type in _IMAGE_SUFFIXES:
        return "jpg" if content_type == "jpeg" else content_type
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix if suffix in _IMAGE_SUFFIXES else "jpg"


def _image_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": MobileDeScraper.user_agent},
    )


def ensure_local_images(source: str, source_listing_id: str, urls: list[str]) -> dict:
    """Garantiza las imágenes locales y devuelve `{images, downloaded, failed}`.

    `images` solo incluye las que están disponibles localmente:
    `[{"url": ..., "local_path": ...}]`.
    """
    if not urls:
        return {"images": [], "downloaded": 0, "failed": 0}

    manifest = _load_manifest(source, source_listing_id)

    def _available(url: str) -> bool:
        rec = manifest.get(url)
        return bool(rec and rec.get("status") == "ok" and Path(rec.get("local_path") or "").exists())

    pending = [url for url in urls if not _available(url)]
    downloaded, failed = 0, 0

    if pending:
        with _image_client() as client:
            for index, url in enumerate(urls, start=1):
                if _available(url):
                    continue
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    ext = _guess_extension(url, response)
                    location = save_image(response.content, source, source_listing_id, f"{index:02d}.{ext}")
                    if location is None:
                        raise RuntimeError("fallo al guardar la imagen")
                    manifest[url] = {"local_path": location, "status": "ok"}
                    downloaded += 1
                except (httpx.HTTPError, RuntimeError) as exc:
                    logger.warning("Imagen %s de %s/%s falló: %s", url, source, source_listing_id, exc)
                    manifest[url] = {"local_path": None, "status": "failed", "error": str(exc)}
                    failed += 1

        save_manifest(
            source,
            source_listing_id,
            {
                "source": source,
                "source_listing_id": source_listing_id,
                "images": [
                    {"source_url": url, "local_path": rec.get("local_path"), "status": rec.get("status"), "error": rec.get("error")}
                    for url, rec in manifest.items()
                ],
            },
        )

    images = [
        {"url": url, "local_path": manifest[url]["local_path"]}
        for url in urls
        if _available(url)
    ]
    return {"images": images, "downloaded": downloaded, "failed": failed}
