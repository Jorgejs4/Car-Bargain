"""Acceso histórico a mobile.de vía Wayback Machine (archive.org).

Sirve cuando el scraping live está bloqueado por IP (403 por WAF), alimenta la
Fase 2 (datos históricos de precios) y actúa como "canario" de cambios de schema:
si `parser` deja de reconocer un snapshot reciente, algo cambió en la fuente.

El `scraped_at` de los `NormalizedListing` se fija a la fecha del snapshot, no a
"ahora", para no contaminar la serie histórica de precios.
"""

import logging
import re
from datetime import datetime, timezone

import httpx

from scrapers.base.models import NormalizedListing
from scrapers.mobile_de.mapper import MobileDeMapper
from scrapers.mobile_de.parser import MobileDeParser

logger = logging.getLogger(__name__)

CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB = "https://web.archive.org/web/"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

_WAYBACK_URL_PREFIX = re.compile(r"^https://web\.archive\.org/web/\d+(?:id_)?/", re.IGNORECASE)


class WaybackError(RuntimeError):
    """Fallo al consultar el Wayback Machine."""


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


class MobileDeHistoricalScraper:
    """Recolecta anuncios de mobile.de a partir de snapshots de archive.org."""

    def __init__(
        self,
        parser: MobileDeParser | None = None,
        mapper: MobileDeMapper | None = None,
        *,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.parser = parser or MobileDeParser()
        self.mapper = mapper or MobileDeMapper()
        self._client = client or httpx.Client(
            headers=dict(_DEFAULT_HEADERS), timeout=timeout, follow_redirects=True
        )

    def list_snapshots(
        self,
        url: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Devuelve snapshots del CDX API ordenados de más reciente a más antiguo."""
        params = {
            "url": url,
            "output": "json",
            "limit": str(limit),
            "sort": "reverse",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,mimetype",
        }
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        response = self._client.get(CDX_API, params=params)
        response.raise_for_status()
        rows = response.json()
        if not rows or len(rows) < 2:
            return []
        header = rows[0]
        return [dict(zip(header, row)) for row in rows[1:]]

    def fetch_snapshot(self, timestamp: str, url: str) -> str:
        """Descarga el HTML de un snapshot concreto (`id_` evita el re-write de archive.org)."""
        target = f"{WAYBACK_WEB}{timestamp}id_/{url}"
        response = self._client.get(target)
        if response.status_code == 403 or "Zugriff verweigert" in response.text:
            raise WaybackError(f"El snapshot {timestamp} devolvió acceso denegado")
        response.raise_for_status()
        return response.text

    def run(self, url: str, timestamp: str) -> list[NormalizedListing]:
        html = self.fetch_snapshot(timestamp, url)
        listings = self._map_all(html)
        scraped_at = _parse_timestamp(timestamp)
        return [listing.model_copy(update={"scraped_at": scraped_at}) for listing in listings]

    def run_latest(self, url: str, from_ts: str | None = None) -> list[NormalizedListing]:
        snapshots = self.list_snapshots(url, from_ts=from_ts, limit=1)
        if not snapshots:
            raise WaybackError("No hay snapshots disponibles para la URL")
        return self.run(url, snapshots[0]["timestamp"])

    def _map_all(self, html: str) -> list[NormalizedListing]:
        listings: list[NormalizedListing] = []
        for record in self.parser.parse(html):
            try:
                listing = self.mapper.map(record)
            except (TypeError, ValueError) as exc:
                logger.warning("Anuncio %s de mobile_de (wayback) descartado: %s", record.get("id"), exc)
                continue
            image_urls = [_WAYBACK_URL_PREFIX.sub("", url) for url in listing.image_urls]
            listings.append(listing.model_copy(update={"image_urls": image_urls}))
        return listings
