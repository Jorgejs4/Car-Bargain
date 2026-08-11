"""Endpoints públicos de vehículos (Fase 4, API REST)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import MarketStats, VehicleDetail, VehicleHistoryEntry
from app.services import listings_query

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


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
