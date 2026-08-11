# Plan de implementación

Decisiones fijadas:

- Docker Compose (PostgreSQL + PostGIS, Redis).
- Backend first: API + scraper + DB before the frontend.
- Python 3.12 with `pip` + `venv` + `requirements.txt`.
- Primer scraper solo **mobile.de**.
- Monorepo: `backend/`, `frontend/`, `ml/`, `infrastructure/`, `docs/`, `scripts/`.
- **100% gratuito:** toda la infraestructura usa free tiers (Oracle Cloud Always Free, Cloudflare R2, GitHub Actions en repo público). Nada de pago.
- **Detección de daños desde el inicio:** señales de texto + campo estructurado + visión por computadora (CLIP zero-shot open-source local). Desvío deliberado de `ARCHITECTURE.md` (que la dejaba fuera del MVP).

Cada fase termina verificable (tests pasan, servicios arrancan).

---

## Fase 0 — Infraestructura y esqueleto del monorepo

**Objetivo:** monorepo con backend FastAPI arrancable y servicios de datos en Docker.

- Estructura: `backend/` (app/, scrapers/, workers/, migrations/, tests/), `scripts/`, `docs/`, `.env.example`, `.gitignore`, `LICENSE`.
- `docker-compose.yml`: `postgres` (imagen `postgis/postgis`), `redis`.
- Backend: venv + `requirements.txt` (FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, psycopg, Celery, redis, Playwright, pytest, ruff, uvicorn).
- FastAPI base: `app/main.py`, `app/core/` (config vía `.env`), `app/db/` (session + base), endpoint `/health` que comprueba DB y Redis.
- Alembic inicializado; `.env.example` con `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.
- Scripts de dev: `scripts/setup.ps1`, `scripts/dev.ps1`.
- **Aceptación:** `GET /health` → 200 con DB/Redis OK; `alembic upgrade head` aplica sobre Postgres.

## Fase 1 — Modelo de datos base (migraciones)

**Objetivo:** tablas núcleo del dominio con sus invariantes.

- Migraciones Alembic para `vehicles`, `listings`, `listing_snapshots`, `listing_events`.
- Invariantes garantizados a nivel de esquema y servicio:
  - `UNIQUE(source, source_listing_id)` en `listings`.
  - `listing_snapshots` solo append (nunca sobrescribir).
  - `status` en `ACTIVE/STALE/REMOVED/SOLD` (check constraint).
- Modelos SQLAlchemy + schemas Pydantic (Pydantic es la frontera, no los modelos ORM).
- **Aceptación:** migraciones idempotentes; tests de unicidad y append-only.

## Fase 2 — Scraper mobile.de (pipeline completo)

**Objetivo:** anuncios reales de mobile.de → normalizados → DB con histórico e imágenes.

- `scrapers/base/`: contrato `NormalizedListing` (Pydantic; incluye `image_urls: list[str]`), interfaces `Scraper`/`Parser`/`Mapper`/`Validator`.
- `scrapers/mobile_de/`: `scraper.py` (Playwright, paginación, robustez), `parser.py`, `mapper.py`.
- Ingesta (servicio `app/services/ingest.py`):
  - upsert de `listings` por clave única; primera vista → `LISTED`;
  - snapshot nuevo en cada scrape (nunca sobrescribir); eventos `PRICE_CHANGED`/`MILEAGE_CHANGED`/`DESCRIPTION_CHANGED` si hay deltas;
  - `first_seen_at`/`last_seen_at`/`updated_at`.
  - Descarga de imágenes a `raw/{source}/...` (R2 en Fase 10).
- **Señales de texto + campo estructurado** → `condition_signals` (JSONB en el snapshot, con `confidence` + `source`):
  - Lexicón DE (mobile.de): `Unfallfrei`, `Unfallwagen`, `Motorschaden`, `Hagelschaden`, `Rost`, `Kratzer`, `Beule/Delle`, `lackiert/Neulackierung`.
  - Si la fuente expone un campo estructurado de accidentes, se prioriza sobre el texto.
  - Ausencia de palabras ⇒ bucket `unknown` (nunca asumir buen estado).
- Status tracking job: `update_listing_status` con `last_seen_at` y umbrales configurables por fuente (STALE 6h / REMOVED 48h).
- Celery: tarea `scrape_mobile_de` + beat (15 min), lock Redis (`scraper:mobile_de:running`).
- Observabilidad mínima por ejecución.
- Tests: parsers con fixtures HTML reales (sin red).
- **Aceptación:** una ejecución deja listings + snapshots + eventos + imágenes + señales de texto en DB; dos ejecuciones seguidas no duplican.

## Fase 3 — Detección de daños visuales (CV)

**Objetivo:** daño visual por fotografía desde el inicio, alimentando riesgo y precio.

- Motor **CLIP zero-shot** (open_clip + torch CPU) — sin dataset de entrenamiento; clasifica por foto: `sin daños / roces / abolladura / óxido / cristal roto / repintado`, con probabilidad.
- Deps en `requirements-cv.txt` (torch, open_clip_torch, pillow) para no engordar el entorno base.
- Tarea Celery `analyze_listing_images` (descarga → analiza → guarda en `photo_analyses` con `model_version` y `analyzed_at`); worker separado para no bloquear la ingesta.
- Agregación por listing → `photo_damage_prob`, `has_visible_damage`, `damage_types` dentro de `condition_signals`.
- **Contradicciones texto/foto** (ej. "sin accidentes" + foto dañada): sube el Risk Score y marca `needs_review=True`.
- Umbrales configurables (`DAMAGE_PROB_MIN`, `CONTRADICTION_TOLERANCE`).
- YOLO fine-tune queda como evolución cuando se acumule dataset etiquetado.
- **Aceptación:** fotos reales de un listing producen `photo_analyses` con resultado + probabilidad; la contradicción detectada marca revisión.

## Fase 4 — API REST

**Objetivo:** el backend es consumible por el frontend.

- `GET /api/v1/listings` (+filtros: brand, model, country, price_min/max, mileage_max, year_min, fuel, transmission, seller_type), paginado.
- `GET /api/v1/listings/{id}`, `GET /api/v1/listings/active`.
- `GET /api/v1/vehicles/{id}`, `/vehicles/{id}/history`, `/vehicles/{id}/market`.
- `POST /internal/scrapers/mobile-de` (disparo manual, protegido, no público).
- Exponer `condition_signals` y `needs_review` en el detalle de listing.
- **Regla:** dashboard consulta solo `status='ACTIVE'`; no mezclar live con histórico.
- Tests de API (TestClient) con DB de test aislada.

## Fase 5 — Normalización y Vehicle Matching (v1)

**Objetivo:** identificar el mismo vehículo/variante entre anuncios.

- Normalización de texto (ej. `320 d` → `320d`), diccionarios, reglas, fuzzy (rapidfuzz).
- Asignar `vehicle_id` a listings; dedupe entre anuncios de la misma fuente.
- Conservar `raw_value/normalized_value/confidence/source`.
- **Aceptación:** suite de casos de matching (BMW 320d xDrive M Sport vs M Sportpaket).

## Fase 6 — Mercado español + valoración baseline

**Objetivo:** comparar precio europeo vs español sin ML todavía.

- Segundo scraper: **coches.net** (España) + lexicón ES para señales de texto (`sin accidentes`, `golpes`, `roces`, `abolladuras`, `rayado`, `chocado`, `repintado`, `dado de baja`).
- Valoración baseline: mediana, percentiles P10/P50/P90 y comparables por variante/año/km en mercado ES.
- La valoración ES usa `condition_bucket` (damage_free / cosmetic / significant / unknown).
- Tabla `price_predictions` (persistir valoraciones).
- **Aceptación:** para un BMW 320d de DE, endpoint devuelve precio ES estimado con intervalo y confianza, corregido por estado.

> **Estado real (agosto 2026):** scrapers live de **coches.net** y **AutoScout24 (ES)**
> implementados, testeado el pipeline end-to-end e integrados en Celery/beat/API interna
> (ver `docs/SCRAPERS.md`). **Pendiente:** valoración baseline (percentiles y
> `price_predictions`) y corrección por `condition_bucket`.

## Fase 7 — Import Cost Engine + Deal Engine + Deal Score

**Objetivo:** margen real tras todos los costes.

- Reglas fiscales versionadas (país+año) en tablas `tax_rules`; prohibido hardcodear.
- `transport_rates` y cálculo con PostGIS (distancia origen→ES).
- Tabla `repair_estimates`: tipo de daño → rango de coste, por mercado, versionadas como `tax_rules`; alimenta la partida **"Repairs"** del beneficio.
- Deal Engine: beneficio esperado (venta ES − compra − transporte − impuestos − ITV − documentación − reparaciones − preparación − costes financieros), ROI = profit / capital invertido.
- `deal_scores` con pesos propuestos (35% margen, 20% confianza, 15% liquidez, 10% calidad, 10% facilidad importación, 10% riesgo).
- El daño detectado (texto/foto) reduce el beneficio y sube el Risk Score.
- **Aceptación:** caso BMW 320d reproduce el ejemplo del README; un listing con daño relevante baja beneficio y score.

## Fase 8 — Frontend (dashboard web)

**Objetivo:** aplicación web real sobre la API.

- `frontend/`: Next.js + TypeScript + Tailwind + shadcn/ui.
- Vistas: dashboard de deals activos (tarjetas con precio DE/ES, coste importación, beneficio, ROI, score, risk), detalle de listing, filtros.
- **Badges de daños** en las tarjetas (probabilidad y tipo) y sección de "revisión manual" para listings `needs_review`.
- Estado: SWR/React Query; tipos generados desde los schemas de la API.
- **Aceptación:** el dashboard muestra solo `status='ACTIVE'`, enlaza al anuncio real y refleja el estado de daños.

## Fase 9 — ML de valoración

**Objetivo:** sustituir baseline por modelo con incertidumbre.

- Datasets construidos temporalmente (TRAIN pasado → VALIDATION → TEST reciente); nunca split aleatorio si hay data leakage.
- Baseline → RandomForest → LightGBM → LightGBM quantile (P10/P50/P90).
- Features del doc §18 **más `condition_signals`** (texto + foto: `condition_bucket`, flags de accidente/óxido/repintado, `photo_damage_prob`) → el modelo aprende el descuento real por estado.
- Métricas MAE/RMSE/MAPE/coverage.
- Job Celery `train_price_model` (semanal).
- **Aceptación:** modelo con métricas documentadas y sin leakage temporal.

## Fase 10 — Alertas, notificaciones, seguridad y observabilidad

**Objetivo:** cerrar el ciclo con notificaciones personalizables y endurecer.

### Sistema de notificaciones y filtros de usuario

Tablas nuevas: `users`, `alert_preferences`, `notifications`.

Filtros por usuario (endpoint CRUD `user/me/preferences`):

| Grupo | Parámetros |
|---|---|
| Presupuestos | `max_purchase_price` (máx. compra del coche) · `max_total_cost` (máx. coste total con transporte+impuestos) |
| Rentabilidad | `min_profit` · `min_roi` · `min_deal_score` · `max_risk_score` |
| Técnicos | `fuel` · `transmission` · `max_mileage` · `year_min` |
| Canales | `notify_web: bool` · `notify_email: bool` |

Un anuncio se notifica solo si cumple **todos** los filtros configurados.

Flujo:
1. Tras cada ciclo de scraping, el job evalúa solo listings `ACTIVE` que cumplan los filtros.
2. **Dedupe:** clave `(user_id, listing_id)` → un deal nuevo se notifica una vez; si el precio/score cambia se re-evalúa y emite `PRICE_CHANGED` (máx. 1 por cambio de precio).
3. Web: fila `pending` → la UI la muestra en una campanita y la marca `read`.
4. Email: tarea Celery envía por SMTP gratuito (Gmail app password / Resend free) y marca `sent`; fallos quedan `pending` para reintento.
5. **Contenido:** beneficio esperado + intervalo probable + confianza (nunca como certeza).

Endpoints:
- `GET/PUT /api/v1/users/me/preferences`
- `GET /api/v1/users/me/notifications` (+ `?unread=true`)
- `POST /api/v1/users/me/notifications/{id}/read`

### Resto

- Auth básica (API interna), rate limiting, validación de inputs.
- Métricas (`scraper_success_rate`, `parse_success_rate`, `new/removed_listings`…), logs estructurados, Sentry (free tier).
- Raw data e imágenes a Cloudflare R2 (free tier) con partición `raw/{source}/{YYYY}/{MM}/{DD}/`.
- **Aceptación:** alerta real cuando un listing supera los umbrales del usuario (web + email); raw en R2.

## Fase 11 — Más fuentes y despliegue

**Objetivo:** escalar a MVP completo.

- AutoScout24 (DE + ES), Otomoto (PL) con el mismo `NormalizedListing`; el pipeline CV es compartido.
- Deploy a Oracle Cloud Always Free: Docker Compose en producción, GitHub Actions (lint/test/build), Nginx, HTTPS.
- ClickHouse se evalúa solo si el volumen lo justifica (fuera del MVP).
- **Aceptación:** MVP Alemania→España desplegado y scrapeando en producción.

> **Estado real (agosto 2026):** **AutoScout24 (ES)** ya está implementado y
> funcional en vivo (el mismo parser soporta `.de` cambiando `cy`). **Pendiente:**
> confirmar AutoScout24 DE, Otomoto (PL) y el despliegue a Oracle Cloud.

---

## Notas transversales

- Cada fase incluye su commit (repo git iniciado con `origin`).
- Las invariantes de `AGENTS.md` se respetan desde el diseño.
- Señales de estado con `confidence` + `source`; nunca asumir buen estado si no hay evidencia (`unknown`).
- CV es una feature más del precio/riesgo, nunca el modelo principal de valoración.
- No se crea infra pesada (ClickHouse/K8s) hasta que el volumen lo justifique.
