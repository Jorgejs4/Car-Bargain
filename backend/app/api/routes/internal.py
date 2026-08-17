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


@router.get("/worker-status")
def worker_status() -> dict:
    """Resumen público de solo lectura del estado del Worker.

    No expone argumentos, resultados ni credenciales: únicamente el estado
    operativo y el número de tareas que están ejecutándose o esperando en la
    ventana de prefetch de Celery.
    """
    inspector = celery_app.control.inspect(timeout=2)
    ping = inspector.ping() or {}
    active_by_worker = inspector.active() or {}
    reserved_by_worker = inspector.reserved() or {}
    scheduled_by_worker = inspector.scheduled() or {}
    stats_by_worker = inspector.stats() or {}

    def task_counts(tasks_by_worker: dict) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tasks in tasks_by_worker.values():
            for task in tasks or []:
                name = task.get("name") or task.get("type") or "desconocida"
                counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    active = task_counts(active_by_worker)
    queued = task_counts(reserved_by_worker)
    scheduled = task_counts(scheduled_by_worker)
    return {
        "online": bool(ping),
        "workers": len(ping),
        "active_count": sum(active.values()),
        "queued_count": sum(queued.values()),
        "scheduled_count": sum(scheduled.values()),
        "active": active,
        "queued": queued,
        "scheduled": scheduled,
        "concurrency": sum(
            int(worker.get("pool", {}).get("max-concurrency", 0) or 0)
            for worker in stats_by_worker.values()
        ),
        "note": "queued refleja las tareas reservadas por Celery (prefetch), no todo el contenido del broker.",
    }
