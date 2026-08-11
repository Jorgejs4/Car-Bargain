from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.internal import router as internal_router
from app.api.routes.listings import router as listings_router
from app.api.routes.vehicles import router as vehicles_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="API de detección de oportunidades de importación de vehículos Europa → España.",
)

app.include_router(health_router)
app.include_router(listings_router)
app.include_router(vehicles_router)
app.include_router(internal_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"app": settings.app_name, "status": "ok"}
