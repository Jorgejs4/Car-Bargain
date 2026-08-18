"""Descarga de descripción de anuncio y extracción de texto de detalle."""

import logging

import httpx
from scrapers.base.detail import extract_detail_text

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
        return extract_detail_text(response.text)


def translate_to_spanish(text: str | None, source_lang: str) -> str | None:
    """Traducción gratuita y best-effort para descripciones de portales europeos.

    Si el servicio no está disponible se conserva el original; no se pierde nunca
    información del anuncio por un fallo de traducción.
    """
    if not text or source_lang == "es":
        return text
    chunks = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]
    translated: list[str] = []
    try:
        with httpx.Client(timeout=12.0) as client:
            for chunk in chunks:
                response = client.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": chunk[:450], "langpair": f"{source_lang}|es"},
                )
                response.raise_for_status()
                value = response.json().get("responseData", {}).get("translatedText")
                translated.append(value if isinstance(value, str) and value.strip() else chunk)
    except (httpx.HTTPError, ValueError, TypeError):
        return text
    return "\n\n".join(translated) if translated else text
