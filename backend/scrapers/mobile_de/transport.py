"""Transporte HTTP con impersonación TLS para mobile.de (curl_cffi + httpx).

Akamai en mobile.de rechaza el tráfico de datacenter y exige huella TLS
idéntica a la de un navegador real. Este módulo intenta curl_cffi (que emula
el TLS de Chrome) como primera opción y cae a httpx. Si se configura un
`scraper_proxy` residencial se usa en ambas vías.
"""

import logging
import time

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.mobile.de/",
}

_RETRIES = 3
_RETRY_BACKOFF = 2.0


def _try_curl_cffi(
    url: str,
    headers: dict[str, str],
    timeout: float,
    proxy: str | None,
) -> httpx.Response:
    """Intenta el fetch con curl_cffi (impersonación TLS Chrome).

    Si curl_cffi no está instalado o falla, propaga la excepción para
    que el llamador pueda caer a httpx.
    """
    from curl_cffi import requests as cr

    session = cr.Session(impersonate="chrome124")
    response = None
    last_err: Exception | None = None

    for _attempt in range(_RETRIES):
        try:
            response = session.get(
                url,
                headers={
                    k: v
                    for k, v in headers.items()
                    if k.lower() != "content-length"
                },
                timeout=timeout,
                proxy=proxy or None,
            )
            if response.status_code != 403:
                return httpx.Response(
                    status_code=response.status_code,
                    text=response.text,
                    url=str(response.url),
                )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(_RETRY_BACKOFF)

    if response is not None and response.status_code == 403:
        raise RuntimeError(
            "mobile.de devolvió 403 (Akamai). "
            "Se necesita un proxy residencial; configúralo en SCRAPER_PROXY del .env "
            "o usa el histórico vía Wayback como fallback."
        )
    if last_err:
        raise last_err
    raise RuntimeError("curl_cffi falló sin excepción en los reintentos")


def _try_httpx(
    url: str,
    headers: dict[str, str],
    timeout: float,
    proxy: str | None,
) -> httpx.Response:
    """Fallback con httpx cuando curl_cffi no está disponible."""
    client = httpx.Client()
    for _attempt in range(_RETRIES):
        try:
            response = client.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
                proxy=proxy or None,
            )
            if response.status_code != 403:
                return response
        except Exception:  # noqa: BLE001, S110
            pass
        time.sleep(_RETRY_BACKOFF)
    raise RuntimeError("mobile.de devolvió 403 persistente tras reintentos")


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    proxy: str | None = None,
) -> httpx.Response:
    """GET a la URL con mejor-esfuerzo anti-Akamai.

    - Si `proxy` no se pasa explícitamente, se toma de `settings.scraper_proxy`.
    - Intenta curl_cffi primero (impersonación TLS Chrome); si no, httpx.
    - 403 persistente tras reintentos → RuntimeError con diagnóstico.
    """
    effective_headers = {**_DEFAULT_HEADERS, **(headers or {})}
    effective_proxy = proxy or settings.scraper_proxy

    try:
        return _try_curl_cffi(url, effective_headers, timeout, effective_proxy)
    except Exception as exc:  # noqa: BLE001
        logger.warning("curl_cffi falló (%s), intentando httpx", exc)

    return _try_httpx(url, effective_headers, timeout, effective_proxy)
