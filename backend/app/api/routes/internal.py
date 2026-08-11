"""Endpoints internos (disparo manual de jobs, protegidos, no públicos)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from workers.celery_app import celery_app

from app.api.deps import require_internal_key

router = APIRouter(prefix="/internal", tags=["internal"])


class ScraperTrigger(BaseModel):
    max_pages: int = Field(1, ge=1, le=50)
    save_raw_response: bool = True
    enqueue_image_downloads: bool = True


@router.post(
    "/scrapers/mobile-de",
    summary="Disparo manual del scraper de mobile.de",
    dependencies=[Depends(require_internal_key)],
)
def trigger_mobile_de(payload: ScraperTrigger | None = None) -> dict:
    params = payload.model_dump() if payload else ScraperTrigger().model_dump()
    result = celery_app.send_task("scrape.mobile_de", kwargs=params)
    return {"status": "enqueued", "task_id": result.id, "params": params}
