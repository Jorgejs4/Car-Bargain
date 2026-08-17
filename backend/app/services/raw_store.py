"""Almacenamiento de raw (páginas HTML e imágenes) de los scrapers.

- Por defecto: sistema de archivos local en `backend/data/raw/<source>/...`.
- Opcional: Cloudflare R2 (free tier) si `r2_endpoint` está configurado en `.env`.

Nunca lanza: si falla el guardado solo se registra, para no romper la ingesta.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def _r2_client():
    from app.core.config import settings

    if not settings.r2_endpoint:
        return None
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 no está instalado; el raw se guardará solo local")
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
    )


def _store(key: str, body: bytes) -> str | None:
    """Guarda `body` bajo `key` en R2 (si configurado) o local. Devuelve la localización."""
    client = _r2_client()
    try:
        if client is not None:
            from app.core.config import settings

            client.put_object(Bucket=settings.r2_bucket, Key=key, Body=body)
            location = f"s3://{settings.r2_bucket}/{key}"
            logger.info("Raw guardado en R2: %s", location)
            return location

        path = _DEFAULT_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        logger.info("Raw guardado local: %s", path)
        return str(path)
    except Exception:
        logger.exception("No se pudo guardar el raw: %s", key)
        return None


def save_raw(content: str, source: str, name: str) -> str | None:
    """Guarda una respuesta HTML y devuelve su localización, o `None` si falló."""
    stamp = datetime.now(timezone.utc)
    date_dir = Path(stamp.strftime("%Y")) / stamp.strftime("%m") / stamp.strftime("%d")
    filename = f"{stamp.strftime('%H%M%S')}_{name}"
    key = f"{source}/{date_dir}/{filename}"
    return _store(key, content.encode("utf-8"))


def save_image(content: bytes, source: str, listing_id: str, filename: str) -> str | None:
    """Guarda una imagen en `raw/<source>/images/<listing_id>/<filename>`."""
    key = f"{source}/images/{listing_id}/{filename}"
    return _store(key, content)


def save_manifest(source: str, listing_id: str, content: dict) -> str | None:
    """Guarda el `manifest.json` de una descarga de imágenes (origen -> ruta local)."""
    key = f"{source}/images/{listing_id}/manifest.json"
    body = json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")
    return _store(key, body)
