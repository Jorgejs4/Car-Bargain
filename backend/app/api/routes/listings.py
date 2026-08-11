"""Endpoints públicos de listings (Fase 4, API REST).

Regla del dashboard: por defecto solo `status='ACTIVE'`; nunca mezclar
datos live con históricos.
"""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ListingStatus
from app.schemas import ListingDetail, ListingListItem
from app.schemas.pagination import Page
from app.services import listings_query

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


def listing_filters(
    brand: str | None = Query(None, description="Marca exacta (ej. BMW)"),
    model: str | None = Query(None, description="Modelo, coincidencia parcial (ej. 320d)"),
    country: str | None = Query(None, description="País (ISO 2, ej. DE)"),
    price_min: Decimal | None = Query(None, description="Precio mínimo (último snapshot)"),
    price_max: Decimal | None = Query(None, description="Precio máximo (último snapshot)"),
    mileage_max: int | None = Query(None, description="Kilómetros máximos (último snapshot)"),
    year_min: int | None = Query(None, description="Año mínimo del vehículo"),
    fuel: str | None = Query(None, description="Combustible (ej. diesel)"),
    transmission: str | None = Query(None, description="Cambio (ej. automatic)"),
    seller_type: str | None = Query(None, description="Tipo de vendedor (dealer/private/commercial)"),
    source: str | None = Query(None, description="Fuente (ej. mobile_de)"),
    needs_review: bool | None = Query(None, description="Filtrar por revisión manual pendiente"),
) -> dict:
    return {
        "brand": brand,
        "model": model,
        "country": country,
        "price_min": price_min,
        "price_max": price_max,
        "mileage_max": mileage_max,
        "year_min": year_min,
        "fuel": fuel,
        "transmission": transmission,
        "seller_type": seller_type,
        "source": source,
        "needs_review": needs_review,
    }


def _page(items: list[dict], total: int, page: int, page_size: int) -> Page[ListingListItem]:
    pages = math.ceil(total / page_size) if total else 0
    return Page[ListingListItem](items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("", response_model=Page[ListingListItem], summary="Lista de listings paginada")
def list_listings(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ListingStatus | None = Query(default=ListingStatus.ACTIVE),
    filters: dict = Depends(listing_filters),
) -> Page[ListingListItem]:
    items, total = listings_query.list_listings(
        db, page=page, page_size=page_size, status=status, **filters
    )
    return _page(items, total, page, page_size)


@router.get("/active", response_model=Page[ListingListItem], summary="Listings activos")
def active_listings(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filters: dict = Depends(listing_filters),
) -> Page[ListingListItem]:
    items, total = listings_query.list_listings(
        db, page=page, page_size=page_size, status=ListingStatus.ACTIVE, **filters
    )
    return _page(items, total, page, page_size)


@router.get("/{listing_id}", response_model=ListingDetail, summary="Detalle de un listing")
def get_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingDetail:
    detail = listings_query.get_listing_detail(db, listing_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Listing no encontrado")
    return ListingDetail.model_validate(detail)
