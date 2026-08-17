"""Scraper de mobile.de: fetch del SRP → parser → mapper.

El host real de búsqueda (`suchen.mobile.de`) suele responder 403 a IPs de
datacenter (blindaje Akamai: TLS fingerprinting + challenge JS). Estado verificado
en vivo (2026-08): 403 incluso con User-Agent de navegador desde IP residencial/local.

El scraper propaga esos errores de transporte/fetch (no los silencia) y solo
descarta anuncios individuales que no se pueden mapear.

Vías para un scrape live funcional:
1. `scraper_proxy` (config) con una IP residencial del país (`Accept-Language`
   alineado con la región) → reintentos que resuelven la mayoría de 403 transitorios.
2. Playwright/Puppeteer ejecutando `window.__INITIAL_STATE__` (el parser ya lo entiende).
3. Como fallback está el histórico vía Wayback (`scrapers.mobile_de.wayback`),
   que mantiene la serie de precios aunque el live esté bloqueado.
"""

import logging
import time
import urllib.parse
from collections.abc import Callable

import httpx

from scrapers.base.interfaces import BaseMapper, BaseParser, BaseScraper
from scrapers.base.models import NormalizedListing
from scrapers.mobile_de.mapper import MobileDeMapper
from scrapers.mobile_de.parser import MobileDeParser

logger = logging.getLogger(__name__)

SEARCH_URL = "https://suchen.mobile.de/fahrzeuge/search.html"

_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class MobileDeScraper(BaseScraper):
    """Orquesta la recolección de anuncios de mobile.de."""

    source = "mobile_de"
    user_agent = _DEFAULT_HEADERS["User-Agent"]

    def __init__(
        self,
        parser: BaseParser | None = None,
        mapper: BaseMapper | None = None,
        *,
        client: httpx.Client | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(parser or MobileDeParser(), mapper or MobileDeMapper())
        if client is None:
            from app.core.config import settings

            proxy = proxy or settings.scraper_proxy or None
            client = httpx.Client(
                headers=dict(_DEFAULT_HEADERS),
                timeout=timeout,
                follow_redirects=True,
                proxy=proxy,
            )
        self._client = client

    @staticmethod
    def _build_url(page: int) -> str:
        params = {
            "isSearchRequest": "true",
            "scopeId": "C",
            "sortOption.sortBy": "creationTime",
            "sortOption.sortOrder": "DESCENDING",
            "page": str(page),
        }
        return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    def _fetch(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < _RETRIES - 1:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise
            if response.status_code == 403:
                raise RuntimeError(
                    "mobile.de bloqueó la petición (403). Revisa IP/proxy/user-agent "
                    "(suele requerir IP residencial o Playwright)."
                )
            if response.status_code == 429:
                last_error = RuntimeError("mobile.de limitó la petición (429)")
                if attempt < _RETRIES - 1:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise last_error
            response.raise_for_status()
            return response.text
        raise last_error or RuntimeError("fetch fallido")

    def run(
        self,
        max_pages: int = 1,
        on_page: Callable[[int, str], None] | None = None,
    ) -> list[NormalizedListing]:
        """Scrapea páginas. `on_page(page, html)` se invoca con el raw de cada página."""
        listings: list[NormalizedListing] = []
        for page in range(1, max_pages + 1):
            html = self._fetch(self._build_url(page))
            if on_page is not None:
                on_page(page, html)
            records = self.parser.parse(html)
            for record in records:
                try:
                    listings.append(self.mapper.map(record))
                except (TypeError, ValueError) as exc:
                    logger.warning("Anuncio %s de mobile_de descartado: %s", record.get("id"), exc)
        return listings
