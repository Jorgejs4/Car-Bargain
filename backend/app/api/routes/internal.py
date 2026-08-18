"""Endpoints internos (disparo manual de jobs, protegidos, no públicos)."""

from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from workers.celery_app import celery_app

from app.api.deps import require_internal_key

router = APIRouter(prefix="/internal", tags=["internal"])


class ScraperTrigger(BaseModel):
    max_pages: int = Field(1, ge=1, le=50)
    save_raw_response: bool = True
    enqueue_image_downloads: bool = True


def _trigger(task_name: str, payload: ScraperTrigger | None) -> dict:
    params = payload.model_dump() if payload else ScraperTrigger().model_dump()
    result = celery_app.send_task(task_name, kwargs=params)
    return {"status": "enqueued", "task_id": result.id, "params": params}


@router.post(
    "/scrapers/mobile-de",
    summary="Disparo manual del scraper de mobile.de",
    dependencies=[Depends(require_internal_key)],
)
def trigger_mobile_de(payload: ScraperTrigger | None = None) -> dict:
    return _trigger("scrape.mobile_de", payload)


@router.post(
    "/scrapers/autoscout24",
    summary="Disparo manual del scraper de AutoScout24.es",
    dependencies=[Depends(require_internal_key)],
)
def trigger_autoscout24(payload: ScraperTrigger | None = None) -> dict:
    return _trigger("scrape.autoscout24", payload)


@router.post(
    "/scrapers/coches-net",
    summary="Disparo manual del scraper de coches.net",
    dependencies=[Depends(require_internal_key)],
)
def trigger_coches_net(payload: ScraperTrigger | None = None) -> dict:
    return _trigger("scrape.coches_net", payload)


@router.post(
    "/text/reanalyze/{source}",
    summary="Reanaliza y traduce las descripciones de una fuente",
    dependencies=[Depends(require_internal_key)],
)
def trigger_text_reanalysis(source: str) -> dict:
    result = celery_app.send_task("text.reanalyze_source", kwargs={"source": source})
    return {"status": "enqueued", "task_id": result.id, "source": source}


@router.get("/tasks/{task_id}", dependencies=[Depends(require_internal_key)])
def task_status(task_id: str) -> dict:
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    return response
