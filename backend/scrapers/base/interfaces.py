"""Interfaces base del pipeline de scraping: Parser, Mapper, Scraper."""

from abc import ABC, abstractmethod

from scrapers.base.models import NormalizedListing


class BaseParser(ABC):
    """Extrae registros raw (dicts) desde la respuesta bruta de la fuente."""

    @abstractmethod
    def parse(self, raw: str | dict) -> list[dict]:
        """Devuelve una lista de registros sin mapear."""
        raise NotImplementedError


class BaseMapper(ABC):
    """Convierte un registro raw en un NormalizedListing."""

    @abstractmethod
    def map(self, record: dict) -> NormalizedListing:
        raise NotImplementedError


class BaseScraper(ABC):
    """Orquesta la recolección de una fuente: fetch → parse → map → validate."""

    source: str

    def __init__(self, parser: BaseParser, mapper: BaseMapper) -> None:
        self.parser = parser
        self.mapper = mapper

    @abstractmethod
    def run(self, max_pages: int = 1) -> list[NormalizedListing]:
        raise NotImplementedError
