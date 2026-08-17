# AGENTS.md

## Estado del repositorio

- Documentación de diseño: `README.md` y `ARCHITECTURE.md` (en español). Referencia de producto/técnica; solapan mucho. Si difieren, `ARCHITECTURE.md` es la técnica.
- `docs/IMPLEMENTATION_PLAN.md` — plan por fases, autorizado; incluye desvíos deliberados de los docs (detección de daños con CV desde el inicio, notificaciones con filtros de usuario).
- **Backend en desarrollo (Fases 0-1, pipeline mobile.de de Fase 2, CV de Fase 3 —con torch instalado—, API REST de Fase 4, vehicle matching de Fase 5, frontend de Fase 8, scrapers live de AutoScout24 y coches.net completados).** `ml/` e `infrastructure/` aún no existen. Consulta `docs/SCRAPERS.md` para el estado y guía de cada scraper.
- Escribe toda documentación nueva en español.

## Comandos (Windows / PowerShell, Python 3.12)

- Setup (una vez): `scripts\setup.ps1` — crea `backend\.venv` (Python 3.12), instala deps, copia `.env.example` → `.env`, instala navegador Playwright.
- Deps CV (opcional, Fase 3): `backend\.venv\Scripts\pip.exe install -r backend\requirements-cv.txt` (torch + open_clip; sin ellas `images.analyze` degrada con `cv_unavailable`).
- Dev: `scripts\dev.ps1` — levanta Docker (PostgreSQL+PostGIS en :5432, Redis en :6379), migra y arranca uvicorn en :8000.
- Uvicorn manual: desde `backend/`: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Migraciones (desde la raíz del repo):
  - `backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head`
  - Autogenerar: `backend\.venv\Scripts\alembic.exe -c backend\alembic.ini revision --autogenerate -m "<msg>"`
  - `prepend_sys_path = %(here)s` en `alembic.ini` (importa `app` desde cualquier CWD).
- Tests (desde `backend/`): `.venv\Scripts\python.exe -m pytest tests -q`
- Lint: `backend\.venv\Scripts\python.exe -m ruff check backend`
- Scrape live one-shot (desde tu IP; devuelve 2 si mobile.de bloquea): `scripts\scrape_mobile_de_once.ps1 [--pages N]`
- Scrape histórico (Wayback): `backend\.venv\Scripts\python.exe backend\scripts\scrape_mobile_de_wayback.py [--timestamp YYYYMMDDhhmmss]`
- Guía de scrapers (estado y cómo construir cada uno): `docs/SCRAPERS.md`
- Worker Celery (desde `backend/`): `.venv\Scripts\celery.exe -A workers.celery_app worker --loglevel=info`
- Beat Celery (desde `backend/`): `.venv\Scripts\celery.exe -A workers.celery_app beat --loglevel=info`
- Trigger manual de un scraper (requiere `X-Internal-Key`): `POST /internal/scrapers/{mobile-de|autoscout24|coches-net}` con `{"max_pages": N}`

## Convenciones

- Schemas Pydantic = frontera de la API; nunca exponer modelos ORM directamente.
- Config vía `app/core/config.py` (pydantic-settings, lee `.env` de la raíz del repo).
- DB: servicios en Docker Compose; datos reales en `carbargains` (no usar una DB distinta en dev salvo tests).
- **100% free tier:** Oracle Cloud Always Free + Cloudflare R2 + GitHub Actions (repo público). No introducir servicios de pago.
- Detección de daños (CV, CLIP zero-shot) es una feature más de precio/riesgo, nunca el modelo principal.

## Invariantes del dominio (no violar)

- `REMOVED != SOLD`; no inferir venta de una desaparición.
- Nunca sobrescribir `listing_snapshots`; solo añadir filas.
- Identidad de anuncio: clave única `(source, source_listing_id)`.
- No mezclar datos live con históricos; el dashboard solo muestra `status = 'ACTIVE'`.
- Split train/validation/test temporal (pasado → reciente), nunca aleatorio si hay riesgo de data leakage.
- Reglas fiscales versionadas (país + año); prohibido hardcodear valores como `registration_tax = 500`.
- No marcar `REMOVED` tras una única ausencia: usar `last_seen_at` con umbrales configurables por fuente (STALE 6h, REMOVED 48h).
- Un LLM no debe ser el modelo principal de valoración de precios.
- Cada scraper es independiente y produce un `NormalizedListing` común.
- Señales de estado con `confidence` + `source`; nunca asumir buen estado si no hay evidencia (`unknown`).

## Estructura

- `backend/app/` — FastAPI (`api/`, `core/`, `db/`, `models/`, `schemas/`, `services/`, `engines/`).
- `backend/scrapers/` — uno por fuente; `base/` con el contrato común.
- `backend/workers/` — Celery (`celery_app.py`).
- `backend/migrations/` — Alembic.
- `frontend/` — Next.js (Fase 8, funcional).
- `ml/`, `infrastructure/` — aún no creados; no asumas que existen.
