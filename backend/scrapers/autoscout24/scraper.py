"""Scraper de AutoScout24 (ES): fetch del SRP → parser → mapper.

A diferencia de mobile.de, AutoScout24.es responde 200 a peticiones HTTP simples
(verificado en vivo 2026-08), pero usa Akamai Bot Manager y puede bloquear ante
ráfagas. Se propaga el error de fetch (403) sin silenciarlo.
"""

import logging
import urllib.parse
from collections.abc import Callable

import httpx

from scrapers.autoscout24.mapper import AutoScout24Mapper
from scrapers.autoscout24.parser import AutoScout24Parser
from scrapers.base.interfaces import BaseMapper, BaseParser, BaseScraper
from scrapers.base.models import NormalizedListing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.autoscout24.es/lst"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class AutoScout24Scraper(BaseScraper):
    """Orquesta la recolección de anuncios de AutoScout24.es."""

    source = "autoscout24"

    def __init__(
        self,
        parser: BaseParser | None = None,
        mapper: BaseMapper | None = None,
        *,
        client: httpx.Client | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(parser or AutoScout24Parser(), mapper or AutoScout24Mapper())
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
            "atype": "C",
            "cy": "E",
            "page": str(page),
        }
        return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    def _fetch(self, url: str) -> str:
        response = self._client.get(url)
        if response.status_code == 403:
            raise RuntimeError(
                "autoscout24 bloqueó la petición (403). Revisa IP/proxy/user-agent "
                "o espera a que se levante el rate-limit."
            )
        response.raise_for_status()
        return response.text

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
                    logger.warning("Anuncio %s de autoscout24 descartado: %s", record.get("id"), exc)
        return listings