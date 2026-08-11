"""Scraper de coches.net (ES): fetch del SRP → parser → mapper.

coches.net devuelve 200 a peticiones HTTP simples (verificado en vivo 2026-08),
pero intercala una página de bloqueo JS ("Ups! Parece que algo no va bien...")
sin `__INITIAL_PROPS__`. El scraper detecta ese bloqueo (página sin anuncios
reconocibles) y lo reporta como error de fetch, no lo silencia.
"""

import logging
import urllib.parse
from collections.abc import Callable

import httpx

from scrapers.base.interfaces import BaseMapper, BaseParser, BaseScraper
from scrapers.base.models import NormalizedListing
from scrapers.coches_net.mapper import CochesNetMapper
from scrapers.coches_net.parser import CochesNetParser, ParseError

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.coches.net/segunda-mano/"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class CochesNetScraper(BaseScraper):
    """Orquesta la recolección de anuncios de coches.net."""

    source = "coches_net"

    def __init__(
        self,
        parser: BaseParser | None = None,
        mapper: BaseMapper | None = None,
        *,
        client: httpx.Client | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(parser or CochesNetParser(), mapper or CochesNetMapper())
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
        if page <= 1:
            return SEARCH_URL
        return f"{SEARCH_URL}?{urllib.parse.urlencode({'pg': str(page)})}"

    def _fetch(self, url: str) -> str:
        response = self._client.get(url)
        if response.status_code == 403:
            raise RuntimeError(
                "coches.net bloqueó la petición (403). Revisa IP/proxy/user-agent."
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
            try:
                records = self.parser.parse(html)
            except ParseError as exc:
                raise RuntimeError(
                    f"coches.net devolvió una página sin __INITIAL_PROPS__ "
                    f"(bloqueo anti-bot?) en la página {page}: {exc}"
                ) from exc
            for record in records:
                try:
                    listings.append(self.mapper.map(record))
                except (TypeError, ValueError) as exc:
                    logger.warning("Anuncio %s de coches_net descartado: %s", record.get("id"), exc)
        return listings