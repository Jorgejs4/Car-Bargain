from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Car Deal Radar API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://carbargains:carbargains@localhost:5432/carbargains"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-change-me"

    r2_endpoint: str | None = None
    r2_access_key: str | None = None
    r2_secret_key: str | None = None
    r2_bucket: str | None = None
    scraper_proxy: str | None = None

    # Clave compartida de los endpoints internos POST /internal/* (no públicos).
    internal_api_key: str = "dev-internal-key-change-me"

    # Orígenes CORS permitidos para la API (dev: el frontend Next.js local).
    cors_origins: list[str] = ["http://localhost:3000"]

    status_stale_after_hours: int = 6
    status_removed_after_hours: int = 48
    # JSON: {"mobile_de": {"stale_after_hours": 6, "removed_after_hours": 48}, ...}
    # Sobrescribe los valores globales por fuente (umbrales configurables por fuente).
    status_thresholds_json: str | None = None

    # TTL del lock Redis anti-solapamiento del scraper (en segundos).
    scraper_lock_ttl_seconds: int = 840

    # Detección de daños visuales (CV, Fase 3).
    cv_enabled: bool = True
    cv_model_name: str = "ViT-B-32"
    cv_pretrained: str = "laion400m_e32"
    # Probabilidad mínima para considerar daño visible en una foto.
    damage_prob_min: float = 0.5
    # Penalización de riesgo cuando el texto dice "sin accidentes" pero la foto muestra daño.
    contradiction_tolerance: float = 0.3


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
