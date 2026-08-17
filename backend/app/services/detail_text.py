"""Descarga de descripción de anuncio y extracción de texto de detalle."""

import logging

import httpx
from scrapers.base.detail import extract_detail_text, is_error_page_title

from app.core.config import settings

logger = logging.getLogger(__name__)

_HEADERS_BY_SOURCE = {
    "autoscout24": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    },
    "coches_net": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    },
    "mobile_de": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    },
}


def fetch_listing_detail(source: str, url: str) -> dict[str, str | None]:
    """Descarga una página de detalle; errores se propagan al task para reintento."""
    headers = _HEADERS_BY_SOURCE.get(source, _HEADERS_BY_SOURCE["autoscout24"])
    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=25.0,
        proxy=settings.scraper_proxy or None,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        extracted = extract_detail_text(response.text)
        if is_error_page_title(extracted.get("title")):
            return {"title": None, "description": None, "seller_comment": None}
        return extracted
