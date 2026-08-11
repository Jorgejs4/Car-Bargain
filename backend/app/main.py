from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de detección de oportunidades de importación de vehículos Europa → España.",
)

app.include_router(health_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"app": settings.app_name, "status": "ok"}
