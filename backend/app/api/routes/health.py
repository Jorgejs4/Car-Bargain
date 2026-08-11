import redis as redis_lib
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> JSONResponse:
    db_status = "ok"
    redis_status = "ok"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - sonda de salud: cualquier fallo debe reportarse
        db_status = "error"

    try:
        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=2)
        client.ping()
    except Exception:  # noqa: BLE001 - sonda de salud: cualquier fallo debe reportarse
        redis_status = "error"

    all_ok = db_status == "ok" and redis_status == "ok"
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"database": db_status, "redis": redis_status},
    )
