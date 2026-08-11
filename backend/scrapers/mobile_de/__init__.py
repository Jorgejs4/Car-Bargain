"""Scraper de mobile.de (coches de ocasión, Alemania).

Fuente documentada como bloqueante para scraping directo desde IPs de datacenter
(403/consent). Los tests usan un fixture sintético con la estructura del SRP;
el parser es tolerante a cambios y a páginas sin resultados (`srp.data = None`).
"""

from scrapers.mobile_de.mapper import MobileDeMapper
from scrapers.mobile_de.parser import MobileDeParser
from scrapers.mobile_de.scraper import MobileDeScraper

__all__ = ["MobileDeMapper", "MobileDeParser", "MobileDeScraper"]
