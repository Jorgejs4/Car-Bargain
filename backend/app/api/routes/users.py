"""Endpoints de preferencias de alerta y notificaciones (Fase 10).

Sin auth completa: hay un único usuario implícito "me" (definido en la fila
de `AlertPreference` con `user_key='me'`). El frontend gestiona sus
preferencias y ve sus notificaciones mediante estos endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    AlertPreference,
    FavoriteListing,
    Listing,
    Notification,
    NotificationStatus,
    SavedSearch,
)
from app.schemas import (
    AlertPreferenceBase,
    AlertPreferenceRead,
    FavoriteRead,
    NotificationRead,
    SavedSearchCreate,
    SavedSearchRead,
)
from app.services.alerts import evaluate_alerts
from app.services.auth import get_user_key
from app.services.email_sender import send_deal_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

def _get_or_create_preference(db: Session, user_key: str) -> AlertPreference:
    pref = db.scalar(select(AlertPreference).where(AlertPreference.user_key == user_key))
    if pref is None:
        pref = AlertPreference(user_key=user_key)
        db.add(pref)
        db.flush()
    return pref


@router.get("/me/preferences", response_model=AlertPreferenceRead, summary="Preferencias de alerta del usuario")
def get_preferences(db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> AlertPreferenceRead:
    pref = _get_or_create_preference(db, user_key)
    db.commit()
    return AlertPreferenceRead.model_validate(pref)


@router.put("/me/preferences", response_model=AlertPreferenceRead, summary="Actualiza preferencias de alerta")
def update_preferences(
    payload: AlertPreferenceBase,
    db: Session = Depends(get_db),
    user_key: str = Depends(get_user_key),
) -> AlertPreferenceRead:
    pref = _get_or_create_preference(db, user_key)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(pref, key, value)
    pref.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pref)
    logger.info("Preferencias actualizadas para %s", pref.user_key)
    return AlertPreferenceRead.model_validate(pref)


@router.post(
    "/me/preferences/evaluate",
    summary="Evalúa los listings activos contra las preferencias y genera notificaciones",
)
def trigger_evaluation(db: Session = Depends(get_db)) -> dict:
    last_id = db.scalar(select(func.max(Notification.id))) or 0
    result = evaluate_alerts(db)
    emails_sent = 0
    pref = db.scalar(select(AlertPreference).where(AlertPreference.user_key == "me"))
    if pref is not None and pref.notify_email and result.notified:
        notifications = db.scalars(
            select(Notification)
            .where(Notification.id > last_id)
            .order_by(Notification.id.asc())
        ).all()
        for notification in notifications:
            if send_deal_email(notification.title, notification.body or {}):
                notification.status = NotificationStatus.SENT.value
                emails_sent += 1
    db.commit()
    return {
        "checked": result.checked,
        "matched": result.matched,
        "notified": result.notified,
        "deduped": result.deduped,
        "emails_sent": emails_sent,
    }


@router.get("/me/notifications", response_model=list[NotificationRead], summary="Notificaciones del usuario")
def list_notifications(
    db: Session = Depends(get_db),
    unread: bool = Query(False, description="Solo no leídas"),
    limit: int = Query(50, ge=1, le=200),
    user_key: str = Depends(get_user_key),
) -> list[NotificationRead]:
    pref = _get_or_create_preference(db, user_key)
    db.commit()
    query = select(Notification).where(Notification.preference_id == pref.id)
    if unread:
        query = query.where(Notification.status != NotificationStatus.READ.value)
    if not pref.notify_web:
        return []
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    notifications = db.scalars(query).all()
    return [NotificationRead.model_validate(n) for n in notifications]


@router.post(
    "/me/notifications/{notification_id}/read",
    summary="Marca una notificación como leída",
)
def mark_as_read(notification_id: int, db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> dict:
    pref = _get_or_create_preference(db, user_key)
    notification = db.get(Notification, notification_id)
    if notification is None or notification.preference_id != pref.id:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    notification.status = NotificationStatus.READ.value
    db.commit()
    return {"id": notification_id, "status": "read"}


@router.get("/me/favorites", response_model=list[FavoriteRead], summary="Lista las ofertas favoritas")
def list_favorites(db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> list[FavoriteRead]:
    favorites = db.scalars(
        select(FavoriteListing)
        .where(FavoriteListing.user_key == user_key)
        .order_by(FavoriteListing.created_at.desc())
    ).all()
    return [FavoriteRead.model_validate(item) for item in favorites]


@router.post("/me/favorites/{listing_id}", response_model=FavoriteRead, summary="Añade una oferta a favoritos")
def add_favorite(listing_id: int, db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> FavoriteRead:
    if db.get(Listing, listing_id) is None:
        raise HTTPException(status_code=404, detail="Listing no encontrado")
    favorite = db.scalar(
        select(FavoriteListing).where(
            FavoriteListing.user_key == user_key,
            FavoriteListing.listing_id == listing_id,
        )
    )
    if favorite is None:
        favorite = FavoriteListing(user_key=user_key, listing_id=listing_id)
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
    return FavoriteRead.model_validate(favorite)


@router.delete("/me/favorites/{listing_id}", status_code=204, summary="Quita una oferta de favoritos")
def remove_favorite(listing_id: int, db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> None:
    favorite = db.scalar(
        select(FavoriteListing).where(
            FavoriteListing.user_key == user_key,
            FavoriteListing.listing_id == listing_id,
        )
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()


@router.get("/me/saved-searches", response_model=list[SavedSearchRead], summary="Lista las búsquedas guardadas")
def list_saved_searches(db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> list[SavedSearchRead]:
    searches = db.scalars(
        select(SavedSearch)
        .where(SavedSearch.user_key == user_key)
        .order_by(SavedSearch.updated_at.desc())
    ).all()
    return [SavedSearchRead.model_validate(item) for item in searches]


@router.post("/me/saved-searches", response_model=SavedSearchRead, summary="Guarda una búsqueda")
def create_saved_search(payload: SavedSearchCreate, db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> SavedSearchRead:
    search = SavedSearch(user_key=user_key, name=payload.name.strip(), filters=payload.filters)
    db.add(search)
    db.commit()
    db.refresh(search)
    return SavedSearchRead.model_validate(search)


@router.delete("/me/saved-searches/{search_id}", status_code=204, summary="Elimina una búsqueda guardada")
def delete_saved_search(search_id: int, db: Session = Depends(get_db), user_key: str = Depends(get_user_key)) -> None:
    search = db.scalar(
        select(SavedSearch).where(
            SavedSearch.id == search_id,
            SavedSearch.user_key == user_key,
        )
    )
    if search is None:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    db.delete(search)
    db.commit()
