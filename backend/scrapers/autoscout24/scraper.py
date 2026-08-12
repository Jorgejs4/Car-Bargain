"""Scraper de AutoScout24: fetch del SRP → parser → mapper.

AutoScout24 responde 200 a peticiones HTTP simples (verificado en vivo 2026-08),
pero usa Akamai Bot Manager y puede bloquear ante ráfagas. La URL base acepta
el parámetro `cy` para filtrar por país europeo (E=ES, D=DE, F=FR, I=IT, etc.).
Se propaga el error de fetch (403) sin silenciarlo.

Para evitar bloqueos se impone un delay entre países (respetuoso con el rate
limit de Akamai) y se itera página a página por país.
"""

import logging
import time
import urllib.parse
from collections.abc import Callable

import httpx

from scrapers.autoscout24.mapper import AutoScout24Mapper
from scrapers.autoscout24.parser import AutoScout24Parser
from scrapers.base.interfaces import BaseMapper, BaseParser, BaseScraper
from scrapers.base.models import NormalizedListing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.autoscout24.es/lst"

# Países de la UE que scrapeamos (cy= parámetro, dominio Accept-Language).
EU_COUNTRIES: list[tuple[str, str]] = [
    ("ES", "es-ES"),
    ("DE", "de-DE"),
    ("FR", "fr-FR"),
    ("IT", "it-IT"),
    ("NL", "nl-NL"),
    ("BE", "nl-BE"),
    ("AT", "de-AT"),
    ("LU", "fr-LU"),
]

_COUNTRY_DELAY_SECONDS = 5.0

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class AutoScout24Scraper(BaseScraper):
    """Orquesta la recolección de anuncios de AutoScout24.

    Admite múltiples países con barrido gradual: 1 página por país cada
    ciclo de beat (por defecto 15 min), delay de 5 s entre países para
    no activar el rate limit de Akamai.
    """

    source = "autoscout24"

    def __init__(
        self,
        parser: BaseParser | None = None,
        mapper: BaseMapper | None = None,
        *,
        client: httpx.Client | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
        country_delay: float = _COUNTRY_DELAY_SECONDS,
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
        self._country_delay = country_delay

    @staticmethod
    def _build_url(page: int, country: str = "E") -> str:
        params = {
            "atype": "C",
            "cy": country,
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
        country_codes: list[str] | None = None,
    ) -> list[NormalizedListing]:
        """Scrapea `max_pages` por cada país indicado.

        - `country_codes`: lista de códigos ISO (default: ["E"] para España).
          Pasar `None` para todos los países de la UE.
        - `on_page(page, html)`: se invoca con el raw de cada página.
        - Entre países se espera `country_delay` segundos para evitar bloqueos.
        """
        if country_codes is None:
            country_codes = ["E"]
        elif country_codes == ["EU"]:
            country_codes = [c for c, _ in EU_COUNTRIES]

        listings: list[NormalizedListing] = []
        single_country = len(country_codes) == 1
        for i, cy in enumerate(country_codes):
            if i > 0:
                logger.info("autoscout24: delay %.0fs entre países", self._country_delay)
                time.sleep(self._country_delay)

            try:
                for page in range(1, max_pages + 1):
                    html = self._fetch(self._build_url(page, cy))
                    if on_page is not None:
                        on_page(page, html)
                    records = self.parser.parse(html)
                    mapped = 0
                    for record in records:
                        try:
                            listings.append(self.mapper.map(record))
                            mapped += 1
                        except (TypeError, ValueError) as exc:
                            logger.warning(
                                "Anuncio %s de autoscout24 descartado: %s",
                                record.get("id"),
                                exc,
                            )
                    logger.info(
                        "autoscout24 cy=%s p=%d → %d anuncios (mapeados: %d)",
                        cy,
                        page,
                        len(records),
                        mapped,
                    )
            except Exception:
                if single_country:
                    raise
                logger.exception("autoscout24 cy=%s falló; se continúa con el siguiente país", cy)

        return listings