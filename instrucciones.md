# Instrucciones — Car Bargains (backend)

Guía paso a paso para levantar la aplicación y probarla en local (Windows / PowerShell, Python 3.12).

---

## 1. Requisitos

- **Docker** (para PostgreSQL + Redis).
- **Python 3.12** en el PATH.
- **Git** (opcional).

## 2. Setup inicial (solo la primera vez)

Desde la raíz del repositorio:

```powershell
scripts\setup.ps1
```

Esto crea `backend\.venv`, instala dependencias, copia `.env.example` → `.env`, e instala el navegador de Playwright.

**Opcional — detección de daños por imagen (CV):** si quieres el análisis real de fotos (CLIP zero-shot), instala las deps CV (descarga ~300 MB):

```powershell
backend\.venv\Scripts\pip.exe install -r backend\requirements-cv.txt
```

Sin ellas la app funciona, pero `images.analyze` devuelve `cv_unavailable`.

## 3. Levantar la infraestructura (PostgreSQL + Redis)

```powershell
docker compose up -d
```

Comprueba que están sanos:

```powershell
docker ps
```

## 4. Levantar la API (uvicorn) en http://localhost:8000

### Opción A — script de dev (recomendado)

```powershell
scripts\dev.ps1
```

Levanta Docker si no estaba, aplica migraciones y arranca uvicorn con recarga (`--reload`) en `http://localhost:8000`. **No arranca el worker** (lo hace la sección 5).

### Opción B — manual

Desde `backend/`:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

> Nota: `scripts\dev.ps1` usa `--app-dir backend`; el manual se ejecuta desde `backend/`.

## 5. Levantar el worker de Celery (procesamiento asíncrono)

El worker ejecuta el scraping, la descarga de imágenes y el análisis CV. Abre **una terminal aparte**.

**Comando correcto (importante):** usa `python -m celery`, NO `celery.exe` — el `.exe` no añade el directorio actual al `sys.path` y falla con `ModuleNotFoundError: No module named 'scrapers'`.

Desde `backend/`:

```powershell
.venv\Scripts\celery.exe -A workers.celery_app worker --loglevel=info --pool=solo --concurrency=1
```

Equivalente con `python -m` (más fiable):

```powershell
.venv\Scripts\python.exe -m celery -A workers.celery_app worker --loglevel=info --pool=solo --concurrency=1
```

Verás `celery@... ready` cuando esté listo.

**Opcional — beat (tareas programadas):** scrape cada 15 min, actualización de status cada 5 min, análisis CV pendiente cada 15 min. En otra terminal:

```powershell
.venv\Scripts\python.exe -m celery -A workers.celery_app beat --loglevel=info
```

## 6. Comprobar que todo responde

| URL | Qué es |
|---|---|
| `http://localhost:8000/health` | Estado de DB y Redis (`{"database":"ok","redis":"ok"}`) |
| `http://localhost:8000/docs` | Swagger UI con todos los endpoints |
| `http://localhost:8000/api/v1/listings` | Lista de listings (solo `status='ACTIVE'` por defecto) |

Ejemplos:

```powershell
# Salud
Invoke-RestMethod http://localhost:8000/health

# Lista con filtros
Invoke-RestMethod "http://localhost:8000/api/v1/listings?brand=BMW&price_max=15000&page_size=10"

# Detalle
Invoke-RestMethod "http://localhost:8000/api/v1/listings/17"

# Mercado de un vehículo
Invoke-RestMethod "http://localhost:8000/api/v1/vehicles/1/market"

# Histórico de precios/km de un vehículo
Invoke-RestMethod "http://localhost:8000/api/v1/vehicles/1/history"
```

## 7. Tener datos reales en la base de datos

El scraping **live** de mobile.de está bloqueado desde muchas IPs (devuelve 403; exit code 2). Para probar con datos reales hay dos caminos:

### Opción A — datos históricos (Wayback Machine), sin red

Ya hay un dataset en `data\wayback\mobile_de_20251205031456.json` (24 anuncios reales de dic-2025).

**1. Ingestar el dataset** (desde la raíz del repo):

```powershell
backend\.venv\Scripts\python.exe backend\scripts\ingest_listings_json.py data\wayback\mobile_de_20251205031456.json
```

Salida esperada: `OK: creados=24 actualizados=0 snapshots=24 eventos=24 omitidos=0`.

**2. (Opcional) Descargar imágenes y analizarlas con CV.** El worker de la sección 5 debe estar corriendo. Encola la descarga + análisis de cada listing:

```powershell
cd backend
.venv\Scripts\python.exe -c "from app.db.session import SessionLocal; from app.models import Listing, ListingStatus; from sqlalchemy import select; from workers.tasks import download_listing_images; db=SessionLocal(); ids=db.scalars(select(Listing.id).where(Listing.status==ListingStatus.ACTIVE)).all(); db.close(); [print('encolado', i, download_listing_images.delay(i).id) for i in ids]"
```

> Las imágenes del CDN de mobile.de de esa captura están **parcialmente caídas** (404); las que siguen vivas se analizan con CV y rellenan `photo_signals`, `needs_review` y `risk_score`. Los 404 quedan registrados en el `manifest.json` de cada listing sin romper nada.

### Opción B — scraping live (solo desde IP no bloqueada)

Desde tu IP residencial (fuera de esta máquina si aquí está bloqueada), en la raíz del repo:

```powershell
scripts\scrape_mobile_de_once.ps1 --pages 1
```

- Exit `0` → OK, dejó el JSON en `data\raw\mobile_de\`.
- Exit `2` → mobile.de te bloquea (403). Usa la opción A o configura `SCRAPER_PROXY` en `.env`.

Con el worker corriendo también puedes disparar el scraper por la API interna:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/internal/scrapers/mobile-de" -Headers @{ "X-Internal-Key" = "dev-internal-key-change-me" } -ContentType "application/json" -Body '{"max_pages": 1}'
```

## 8. Disparar el scraper por Celery (si el live funciona)

```powershell
cd backend
.venv\Scripts\python.exe -c "from workers.tasks import scrape_mobile_de; print(scrape_mobile_de.delay(max_pages=1).id)"
```

## 9. Tests y lint

```powershell
# Tests (desde backend/)
backend\.venv\Scripts\python.exe -m pytest tests -q

# Lint (desde la raíz)
backend\.venv\Scripts\python.exe -m ruff check backend
```

## 10. Logs

- **API**: consola donde corra uvicorn.
- **Worker**: consola donde corra celery.
- **Raw data e imágenes**: `backend\data\raw\mobile_de\`.
- **Resumen de la última ejecución del scraper**: clave Redis `scraper:mobile_de:last_run`.

## Troubleshooting

| Síntoma | Causa / solución |
|---|---|
| `ERR_CONNECTION_REFUSED` en localhost | La API no está corriendo. Arranca uvicorn (sección 4). |
| `No module named 'scrapers'` al lanzar celery | Usaste `celery.exe`. Usa `python -m celery` (sección 5). |
| `scrape_mobile_de_once.ps1` devuelve exit `2` | mobile.de bloquea la IP. Usa Wayback (sección 7A) o un proxy. |
| El worker no procesa tareas | Comprueba Redis (`docker ps`) y que el worker diga `ready`. |
