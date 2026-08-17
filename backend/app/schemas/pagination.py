from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Respuesta paginada de una lista de recursos (Fase 4, API REST)."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
