import secrets

from fastapi import Header, HTTPException

from app.core.config import settings

INTERNAL_KEY_HEADER = "X-Internal-Key"


def require_internal_key(x_internal_key: str = Header(alias=INTERNAL_KEY_HEADER, default="")) -> None:
    """Protege los endpoints `/internal/*` (disparo manual, no públicos).

    Comparación timing-safe contra `internal_api_key` de la configuración.
    """
    if not x_internal_key or not secrets.compare_digest(x_internal_key, settings.internal_api_key):
        raise HTTPException(status_code=401, detail="Clave interna inválida")
