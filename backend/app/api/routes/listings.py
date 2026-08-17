"""Endpoints públicos de listings (Fase 4, API REST).

Regla del dashboard: por defecto solo `status='ACTIVE'`; nunca mezclar
datos live con históricos.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Listing, ListingEvent, ListingEventType, ListingStatus
from app.schemas import ListingDetail, ListingListItem
from app.schemas.pagination import Page
from app.services import listings_query

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


class ListingStatusUpdate(BaseModel):
    status: ListingStatus


@router.patch("/{listing_id}/status", response_model=ListingDetail, summary="Cambiar manualmente el estado")
def update_listing_status(listing_id: int, payload: ListingStatusUpdate, db: Session = Depends(get_db)) -> ListingDetail:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing no encontrado")
    old_status = listing.status
    if old_status != payload.status:
        listing.status = payload.status
        listing.is_historical = payload.status in {ListingStatus.SOLD, ListingStatus.REMOVED}
        db.add(ListingEvent(
            listing_id=listing.id,
            event_type=ListingEventType.STATUS_CHANGED,
            event_timestamp=datetime.now(timezone.utc),
            old_value={"status": old_status.value, "source": "manual"},
            new_value={"status": payload.status.value, "source": "manual"},
        ))
        db.commit()
    detail = listings_query.get_listing_detail(db, listing_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Listing no encontrado")
    return ListingDetail.model_validate(detail)


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
    region: str | None = Query(None, description="Región: ES (España) o EU (resto de Europa)"),
    min_bargain_score: float | None = Query(None, description="Score de oportunidad mínimo (positivo = ganga)"),
    min_absolute_margin: float | None = Query(None, description="Margen absoluto mínimo en € (ahorro estimado)"),
    min_cross_border_margin: float | None = Query(None, description="Margen cross-border mínimo en € (ahorro tras importación)"),
    is_historical: bool | None = Query(None, description="Solo históricos (Wayback) o solo live; por defecto se filtran históricos en ACTIVE"),
    needs_review: bool | None = Query(None, description="Filtrar por revisión manual pendiente"),
    only_clean: bool = Query(
        False,
        description="Solo anuncios con descripción analizada, sin problemas textuales ni daño visual",
    ),
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
        "region": region,
        "min_bargain_score": min_bargain_score,
        "min_absolute_margin": min_absolute_margin,
        "min_cross_border_margin": min_cross_border_margin,
        "is_historical": is_historical,
        "needs_review": needs_review,
        "only_clean": only_clean,
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
    sort_by: str = Query("last_seen", description="Campo: price, mileage, year, last_seen"),
    sort_order: str = Query("desc", description="asc o desc"),
    filters: dict = Depends(listing_filters),
) -> Page[ListingListItem]:
    items, total = listings_query.list_listings(
        db, page=page, page_size=page_size, status=status, sort_by=sort_by, sort_order=sort_order, **filters
    )
    return _page(items, total, page, page_size)


@router.get("/active", response_model=Page[ListingListItem], summary="Listings activos")
def active_listings(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("last_seen", description="Campo: price, mileage, year, last_seen"),
    sort_order: str = Query("desc"),
    filters: dict = Depends(listing_filters),
) -> Page[ListingListItem]:
    items, total = listings_query.list_listings(
        db, page=page, page_size=page_size, status=ListingStatus.ACTIVE, sort_by=sort_by, sort_order=sort_order, **filters
    )
    return _page(items, total, page, page_size)


@router.get("/historical", response_model=Page[ListingListItem], summary="Histórico completo de ofertas")
def historical_listings(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("last_seen", description="Campo: price, mileage, year, last_seen"),
    sort_order: str = Query("desc"),
    filters: dict = Depends(listing_filters),
) -> Page[ListingListItem]:
    """Todas las ofertas (cualquier status y fuente, incluidas las históricas).

    Es el archivo completo: live + Wayback, ACTIVE/STALE/REMOVED/SOLD.
    """
    items, total = listings_query.list_listings(
        db, page=page, page_size=page_size, status=None, sort_by=sort_by, sort_order=sort_order, **filters
    )
    return _page(items, total, page, page_size)


@router.get("/{listing_id}", response_model=ListingDetail, summary="Detalle de un listing")
def get_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingDetail:
    detail = listings_query.get_listing_detail(db, listing_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Listing no encontrado")
    return ListingDetail.model_validate(detail)
