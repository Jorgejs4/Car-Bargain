"""Endpoints públicos de vehículos (Fase 4, API REST)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import MarketStats, VehicleDetail, VehicleHistoryEntry
from app.services import listings_query

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


@router.get("/brands", summary="Lista de marcas con al menos un listing activo")
def list_brands(db: Session = Depends(get_db), q: str | None = Query(None, description="Búsqueda parcial")) -> list[str]:
    return listings_query.list_brands(db, q=q)


@router.get("/models", summary="Modelos de una marca con listings activos")
def list_models(
    db: Session = Depends(get_db),
    brand: str = Query(..., description="Marca exacta"),
) -> list[str]:
    return listings_query.list_models(db, brand=brand)


@router.get("/variants", summary="Lista de versiones de una marca y modelo")
def list_variants(
    db: Session = Depends(get_db),
    brand: str = Query(..., description="Marca exacta"),
    model: str = Query(..., description="Modelo exacto"),
) -> list[str]:
    return listings_query.list_variants(db, brand=brand, model=model)


@router.get("/{vehicle_id}", response_model=VehicleDetail, summary="Detalle de un vehículo")
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleDetail:
    detail = listings_query.vehicle_detail(db, vehicle_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return VehicleDetail.model_validate(detail)


@router.get("/{vehicle_id}/history", response_model=list[VehicleHistoryEntry], summary="Histórico de precios/km del vehículo")
def vehicle_history(vehicle_id: int, db: Session = Depends(get_db)) -> list[VehicleHistoryEntry]:
    entries = listings_query.vehicle_history(db, vehicle_id)
    if entries is None:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return entries


@router.get("/{vehicle_id}/market", response_model=MarketStats, summary="Estadísticas de mercado del vehículo")
def vehicle_market(vehicle_id: int, db: Session = Depends(get_db)) -> MarketStats:
    stats = listings_query.vehicle_market(db, vehicle_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return MarketStats.model_validate(stats)
