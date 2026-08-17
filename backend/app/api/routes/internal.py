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


MAINTENANCE_TASKS = {
    "status": "status.update_listings",
    "images": "images.analyze_pending",
    "text": "text.enrich_pending",
    "score": "score.bargains",
    "import": "import.costs",
    "cross-border": "score.cross_border",
    "alerts": "alerts.evaluate",
}


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


@router.get("/tasks/{task_id}", dependencies=[Depends(require_internal_key)])
def task_status(task_id: str) -> dict:
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    return response


@router.post("/maintenance/{task_name}", dependencies=[Depends(require_internal_key)])
def trigger_maintenance(task_name: str) -> dict:
    celery_name = MAINTENANCE_TASKS.get(task_name)
    if celery_name is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tarea de mantenimiento desconocida")
    result = celery_app.send_task(celery_name)
    return {"status": "enqueued", "task": task_name, "task_id": result.id}


@router.get("/worker-status", dependencies=[Depends(require_internal_key)])
def worker_status() -> dict:
    """Diagnóstico temporal del Worker sin abrir su Shell."""
    inspector = celery_app.control.inspect(timeout=2)
    ping = inspector.ping() or {}
    return {
        "online": bool(ping),
        "ping": ping,
        "active": inspector.active() or {},
        "reserved": inspector.reserved() or {},
        "scheduled": inspector.scheduled() or {},
        "stats": inspector.stats() or {},
    }
