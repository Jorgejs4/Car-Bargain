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

    status_stale_after_hours: int = 6
    status_removed_after_hours: int = 48


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
