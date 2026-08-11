# ARCHITECTURE.md

## 1. Objetivo

Este documento define la arquitectura técnica del proyecto de detección de oportunidades de importación y reventa de vehículos entre mercados europeos y España.

El sistema debe:

1. Recopilar anuncios de múltiples mercados.
2. Normalizar los datos en un modelo común.
3. Identificar variantes y vehículos equivalentes entre fuentes.
4. Mantener histórico completo de anuncios y precios.
5. Separar claramente datos históricos de ofertas actualmente activas.
6. Estimar el valor de mercado europeo y español.
7. Calcular el coste total de importar un vehículo a España.
8. Estimar beneficio, ROI y riesgo.
9. Clasificar las oportunidades mediante un Deal Score.
10. Mostrar únicamente oportunidades activas en el dashboard principal.

---

## 2. Arquitectura general

```text
                        ┌──────────────────────┐
                        │      SOURCES         │
                        │                      │
                        │ mobile.de            │
                        │ AutoScout24          │
                        │ Otomoto               │
                        │ coches.net            │
                        │ otras fuentes         │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │       SCRAPERS       │
                        │     Playwright       │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │      RAW DATA        │
                        │ HTML / JSON / source │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │    NORMALIZATION     │
                        │ Unified schema       │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
             ┌──────────────┐              ┌──────────────┐
             │   VEHICLES   │              │   LISTINGS   │
             └──────┬───────┘              └──────┬───────┘
                    │                             │
                    │                             ▼
                    │                    ┌─────────────────┐
                    │                    │ LISTING EVENTS  │
                    │                    └────────┬────────┘
                    │                             │
                    │                             ▼
                    │                    ┌─────────────────┐
                    │                    │ SNAPSHOTS       │
                    │                    └────────┬────────┘
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                        ┌──────────────────────┐
                        │   DATA / ANALYTICS   │
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┴──────────────────┐
                 ▼                                    ▼
        ┌─────────────────┐                  ┌─────────────────┐
        │ PRICE MODEL     │                  │ MARKET ANALYSIS │
        │ LightGBM        │                  │ historical data │
        └────────┬────────┘                  └─────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ IMPORT COST     │
        │ ENGINE          │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ RISK ENGINE     │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ DEAL ENGINE     │
        │ Deal Score      │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ FastAPI         │
        │ REST API        │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Next.js         │
        │ Dashboard       │
        └─────────────────┘
```

---

# 3. Stack tecnológico

## Backend

- Python 3.12+
- FastAPI
- SQLAlchemy
- Pydantic
- Alembic
- Polars
- Pandas
- scikit-learn
- LightGBM
- Playwright

## Base de datos

- PostgreSQL
- PostGIS
- Redis

## Procesamiento asíncrono

- Celery
- Redis como broker/cache

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

## Infraestructura

- Docker
- Docker Compose
- GitHub Actions
- Oracle Cloud Always Free (free tier)
- Cloudflare R2 (free tier) para almacenamiento de datos raw

## Evolución futura

- ClickHouse para histórico masivo
- OpenSearch para búsquedas avanzadas
- Prometheus/Grafana
- Sentry
- Kubernetes únicamente si el volumen realmente lo justifica

---

# 4. Estructura del repositorio

```text
car-deal-radar/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── engines/
│   │   │   ├── pricing/
│   │   │   ├── import_cost/
│   │   │   ├── risk/
│   │   │   └── deal/
│   │   └── main.py
│   │
│   ├── scrapers/
│   │   ├── base/
│   │   ├── mobile_de/
│   │   ├── autoscout/
│   │   ├── otomoto/
│   │   └── coches_net/
│   │
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks/
│   │
│   ├── migrations/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── types/
│   └── package.json
│
├── ml/
│   ├── datasets/
│   ├── notebooks/
│   ├── features/
│   ├── training/
│   ├── evaluation/
│   └── models/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   └── compose/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── SCRAPERS.md
│   ├── ML.md
│   └── IMPORT_COSTS.md
│
├── scripts/
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

# 5. Modelo de datos

La arquitectura debe distinguir cuatro conceptos principales:

```text
Vehicle
   │
   └── Listing
          │
          ├── ListingEvent
          │
          └── ListingSnapshot
```

## 5.1 vehicles

Representa la identidad normalizada del vehículo.

```sql
CREATE TABLE vehicles (
    id BIGSERIAL PRIMARY KEY,

    brand VARCHAR(100) NOT NULL,
    model VARCHAR(150),
    generation VARCHAR(100),
    variant VARCHAR(150),

    year INTEGER,
    registration_date DATE,

    fuel VARCHAR(50),
    transmission VARCHAR(50),
    drivetrain VARCHAR(50),

    power_kw NUMERIC,
    engine_cc INTEGER,
    co2_g_km NUMERIC,

    body_type VARCHAR(50),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

# 6. listings

Representa un anuncio concreto de una fuente.

```sql
CREATE TABLE listings (
    id BIGSERIAL PRIMARY KEY,

    vehicle_id BIGINT REFERENCES vehicles(id),

    source VARCHAR(50) NOT NULL,
    source_listing_id VARCHAR(255) NOT NULL,

    url TEXT,

    seller_type VARCHAR(30),
    country VARCHAR(2),

    first_seen_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP,

    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(source, source_listing_id)
);
```

### Estados

```text
ACTIVE
STALE
REMOVED
SOLD
```

No se debe interpretar automáticamente `REMOVED` como `SOLD`.

---

# 7. listing_snapshots

Representa el estado del anuncio en un momento determinado.

```sql
CREATE TABLE listing_snapshots (
    id BIGSERIAL PRIMARY KEY,

    listing_id BIGINT NOT NULL REFERENCES listings(id),

    scraped_at TIMESTAMP NOT NULL,

    price NUMERIC(12,2),
    currency VARCHAR(3),

    mileage INTEGER,

    title TEXT,
    description TEXT,

    seller_type VARCHAR(30),

    location TEXT,

    raw_data JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);
```

Ejemplo:

```text
Listing 123

01/08 → 24.900 €
05/08 → 23.900 €
11/08 → 22.900 €
```

Nunca se deben sobrescribir estos datos.

---

# 8. listing_events

Permite representar cambios importantes.

```sql
CREATE TABLE listing_events (
    id BIGSERIAL PRIMARY KEY,

    listing_id BIGINT NOT NULL REFERENCES listings(id),

    event_type VARCHAR(50) NOT NULL,

    event_timestamp TIMESTAMP NOT NULL,

    old_value JSONB,
    new_value JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);
```

Eventos:

```text
LISTED
PRICE_CHANGED
DESCRIPTION_CHANGED
MILEAGE_CHANGED
STATUS_CHANGED
REMOVED
REAPPEARED
```

---

# 9. Separación Historical / Live

Esta es una de las decisiones fundamentales del sistema.

## Historical

Incluye:

- anuncios antiguos
- snapshots
- cambios de precio
- anuncios retirados
- anuncios reaparecidos
- días en mercado
- evolución de precios

Se utiliza para:

- entrenamiento ML
- análisis estadístico
- forecasting
- detección de tendencias
- cálculo de liquidez

## Live

Son únicamente anuncios actualmente disponibles.

El frontend principal debe consultar:

```sql
SELECT *
FROM listings
WHERE status = 'ACTIVE';
```

Después:

```text
ACTIVE
   ↓
Price Model
   ↓
Import Cost Engine
   ↓
Risk Engine
   ↓
Deal Engine
   ↓
Deal Score
```

---

# 10. Detección de anuncios desaparecidos

No se debe marcar un anuncio como eliminado inmediatamente cuando desaparezca en un scraping.

Ejemplo:

```text
08:00 → 50.000 anuncios
10:00 → 49.900 anuncios
```

Esto puede significar:

- anuncios vendidos
- anuncios eliminados
- error del scraper
- bloqueo
- timeout
- cambio de HTML
- error de parsing

Por eso se utiliza `last_seen_at`.

Propuesta inicial:

```text
last_seen < 6h
        ↓
     STALE

last_seen < 48h
        ↓
    REMOVED
```

Los tiempos deben ser configurables por fuente.

---

# 11. Scraping pipeline

Cada fuente tendrá su propio scraper.

```text
Source
  ↓
Scraper
  ↓
Parser
  ↓
Mapper
  ↓
NormalizedListing
  ↓
Validation
  ↓
Database
```

Nunca se debe crear un scraper monolítico.

Incorrecto:

```text
scrape_all_sites.py
```

Correcto:

```text
scrapers/
├── base/
├── mobile_de/
│   ├── scraper.py
│   ├── parser.py
│   └── mapper.py
├── autoscout/
├── otomoto/
└── coches_net/
```

Todos deben producir el mismo objeto lógico:

```python
NormalizedListing
```

Ejemplo:

```python
class NormalizedListing:
    source: str
    source_listing_id: str

    url: str

    brand: str
    model: str
    generation: str | None
    variant: str | None

    year: int | None
    mileage: int | None

    fuel: str | None
    transmission: str | None
    power_kw: float | None
    co2_g_km: float | None

    price: float
    currency: str

    seller_type: str | None

    country: str
    city: str | None

    title: str
    description: str | None

    scraped_at: datetime
```

### 11.1 Estado real: mobile.de bloquea scraping directo

Verificado el 2026-08-11 desde una IP de datacenter:

- `suchen.mobile.de` (host donde vive el SRP con resultados) responde **403 "Zugriff
  verweigert"** para cualquier UA (incluido Googlebot). También bloqueado por HTTP.
- Los endpoints JSON de la SPA (`/api/...`) responden 401/403; `www.mobile.de/fahrzeuge/suche.html`
  devuelve 200 pero **sin SSR de resultados** (`search.srp.data = None`): la SPA carga los
  resultados desde `suchen.mobile.de`, bloqueado.
- Conclusión: el bloqueo es **por IP a nivel de WAF**, no por UA/fingerprint. Para scraping
  live se necesita una IP permitida (residencial) o un proxy configurado en `SCRAPER_PROXY`
  (ver `app/core/config.py`). El scraper propaga el 403 con un mensaje claro en lugar de
  silenciarlo.

### 11.2 Verificación contra datos reales (Wayback Machine)

El parser/mapper se verificaron contra un snapshot **real** de
`suchen.mobile.de/fahrzeuge/search.html` (Wayback Machine, 2025-12-05), que reveló el
schema actual, distinto del clásico:

```text
state.search.srp.data.searchResults.items   # lista de anuncios (mixta)
  ├── ad / topAd / eyecatcherAd             # anuncios reales (tienen "id")
  ├── page1Ads                              # contenedor: .items = anuncios (se aplana)
  └── inlineAdvertising                     # banners publicitarios (se descartan)
```

Campos clave de un anuncio: `id`, `make`, `model`, `title`, `price.grossAmount`,
`price.grossCurrency`, `relativeUrl`, `attr` (strings display en alemán: `fr` matriculación,
`ml` km, `pw` kW, `ft` combustible, `tr` cambio, `cn` país, `loc` ciudad), `contactInfo`
(`typeLocalized` para vendedor), `previewThumbnails`/`previewImage`.

- `backend/tests/fixtures/mobile_de/search_page.html` es ese snapshot real (URLs de
  web.archive.org limpiadas), con 24 anuncios.
- El parser conserva fallback a la estructura antigua `searchResult.ads`.
- `page1Ads` se aplana y `inlineAdvertising` se descarta en `parser.py`.

### 11.3 Pipeline de Fase 2 (scraper mobile.de completo)

- `scrapers/mobile_de/wayback.py` — fuente histórica vía Wayback Machine:
  `list_snapshots` (CDX API) y `fetch_snapshot`; `run_latest(url)` devuelve
  `NormalizedListing` con `scraped_at` = fecha del snapshot (no contamina la serie
  histórica de precios). Script: `backend/scripts/scrape_mobile_de_wayback.py`.
- `scrapers/base/condition.py` — `extract_condition_signals(text, lang, source)`:
  lexicón DE/ES de señales de estado (accidente, daños cosméticos, óxido, repintado,
  motor) con `confidence` + `source`; ausencia de palabras ⇒ `unknown` (nunca asumir
  buen estado). El idioma se deriva del país del anuncio (`DE/AT/CH` → `de`,
  `ES` → `es`).
- `app/services/ingest.py` — `ingest_listings(session, listings)`:
  - `upsert_listing` por `(source, source_listing_id)` (actualiza `last_seen_at`,
    reactiva `REMOVED` → `ACTIVE` con evento `REAPPEARED`).
  - `find_or_create_vehicle` con clave exacta amplia `(brand, model, generation,
    variant, year, fuel, transmission, power_kw)`; el matching fino es Fase 4.
  - Snapshot SIEMPRE append-only (con `condition_signals` de texto + `raw_data`).
  - Eventos `LISTED`, `PRICE_CHANGED`, `MILEAGE_CHANGED`, `DESCRIPTION_CHANGED`.
  - Cada anuncio se procesa en un savepoint: si uno falla solo se omite (`skipped`);
    el resultado incluye los ids afectados para encolar tareas posteriores.
- `workers/tasks.py`:
  - `scrape.mobile_de` — scraper → raw → ingesta, con lock Redis
    (`scraper:mobile_de:running`, TTL configurable) que omite ejecuciones solapadas,
    retry (backoff) solo para errores transitorios de red (el 403 no se reintenta),
    encola la descarga de imágenes y publica un resumen de ejecución en Redis
    (`scraper:mobile_de:last_run`, observabilidad mínima).
  - `images.download` — descarga `image_urls` del último snapshot a
    `raw/<source>/images/<listing_id>/` + `manifest.json` (URL origen → ruta local);
    sin reintentos (403/404 son permanentes), un fallo no bloquea al resto.
  - `status.update_listings` — job de seguimiento de estado por ausencia.
- `app/services/status.py` — `update_listing_statuses(session, source, now)`:
  marca `STALE` (>= umbral de stale) y `REMOVED` (>= umbral de removed) según
  `last_seen_at`, emitiendo `STATUS_CHANGED`/`REMOVED`. Nunca toca `SOLD` (una
  desaparición no es una venta). Umbrales por fuente vía `STATUS_THRESHOLDS_JSON`
  (JSON en `.env`) con fallback a `STATUS_STALE_AFTER_HOURS`/`STATUS_REMOVED_AFTER_HOURS`.
- `app/services/raw_store.py` — raw (HTML e imágenes) en
  `backend/data/raw/<source>/...` por defecto; opcional Cloudflare R2 (`r2_*` en
  `.env`, requiere `boto3`). Nunca lanza (no rompe la ingesta).
- Celery beat (en `workers/celery_app.py`): `scrape.mobile_de` cada 15 min y
  `status.update_listings` cada 5 min.

### 11.4 Detección de daños visuales (Fase 3, CV)

- Motor **CLIP zero-shot** (`app/services/vision.py`, open_clip + torch CPU): clasifica
  cada foto en `sin daños / roces / abolladura / óxido / cristal roto / repintado`
  con probabilidad (softmax sobre prompts). Sin dataset de entrenamiento; YOLO
  fine-tune queda como evolución futura. Imports perezosos: si `torch`/`open_clip`
  no están instalados (`backend/requirements-cv.txt`), la tarea degrada con
  `cv_unavailable` sin romper el pipeline.
- `app/services/listing_images.py` — `ensure_local_images(source, listing_id, urls)`:
  reutilizable por descarga y análisis; idempotente vía `manifest.json`.
- `photo_analyses` (tabla nueva): resultado por foto con `label`, `probability`,
  `model_version`, `analyzed_at`; único por `(listing_id, image_url)`.
- `app/services/photo_analysis.py` — agregación por anuncio → `listings.photo_signals`
  (`photo_damage_prob`, `has_visible_damage`, `damage_types`, `analyzed_images`) y
  `evaluate_damage_risk` → `risk_score` (0..1) + `needs_review`. La contradicción
  texto/foto (ej. "unfallfrei" + foto dañada) sube el riesgo (tolerancia configurable)
  y marca revisión manual. Umbrales: `DAMAGE_PROB_MIN` (0.5), `CONTRADICTION_TOLERANCE` (0.3).
- Tasks Celery: `images.analyze` (análisis + actualización del listing) y
  `images.analyze_pending` (re-encola listings ACTIVE sin analizar, robustez). Beat
  lo ejecuta cada 15 min. `images.download` encola el análisis al terminar.
- **CV nunca es el modelo principal de valoración**: solo alimenta riesgo/`needs_review`
  y, más adelante, el descuento por estado del modelo de precio (invariante del dominio).

---

# 12. Fuente de datos raw

Antes de transformar completamente los datos, se recomienda conservar la información original.

```text
RAW
 ↓
NORMALIZED
 ↓
DATABASE
```

El raw puede almacenarse en:

- JSON
- HTML
- imágenes si son necesarias
- respuestas estructuradas

Storage recomendado:

```text
Cloudflare R2 (free tier)
```

Ejemplo:

```text
raw/
  mobile_de/
    2026/
      08/
        11/
          listing_123.json
```

Esto permite volver a procesar datos sin volver a realizar scraping.

---

# 13. Vehicle Matching

Uno de los problemas más importantes es identificar vehículos equivalentes entre fuentes.

Ejemplo:

```text
mobile.de:
BMW 320 d xDrive M Sport

AutoScout:
BMW 320d xDrive M Sportpaket

coches.net:
BMW Serie 3 320d xDrive M Sport Auto
```

Deben terminar asociados a una representación común.

```text
BMW
└── Serie 3
    └── G20
        └── 320d
            ├── xDrive
            ├── M Sport
            ├── 2020
            └── 190 CV
```

## Estrategia

Primera versión:

1. Normalización de texto.
2. Diccionarios.
3. Reglas.
4. Fuzzy matching.
5. Campos técnicos.
6. VIN cuando exista.

Posteriormente:

- embeddings
- modelos de matching
- LLM para extracción estructurada

El LLM no debe ser la fuente principal de la valoración económica.

---

# 14. Normalización

Ejemplos:

```text
320 D
320d
320-D
320 d
BMW 320 Serie 3 D
```

→

```text
BMW
Serie 3
320d
```

Los valores normalizados deben conservar también el valor original.

```text
raw_value
normalized_value
confidence
source
```

Ejemplo:

```json
{
  "raw_value": "320 d xDrive M Sportpaket",
  "normalized_value": "320d xDrive M Sport",
  "confidence": 0.94,
  "source": "mobile.de"
}
```

---

# 15. Data Quality

Cada dato importante debería tener:

```text
value
source
scraped_at
confidence
```

Ejemplo:

```json
{
  "co2": 121,
  "source": "listing",
  "confidence": 0.95
}
```

Si existe conflicto entre fuentes, se conserva el origen y la confianza.

---

# 16. Price Engine

El sistema tendrá dos valoraciones principales.

```text
European Price
Spanish Price
```

Conceptualmente:

```text
P_europe = f(vehicle, country, market conditions)

P_spain = f(vehicle, Spanish market)
```

No se debe limitar a:

```text
precio medio de anuncios
```

El objetivo es estimar el precio de mercado de un vehículo concreto.

---

# 17. Machine Learning

## Fase 1

Baseline:

```text
median
percentiles
nearest comparable vehicles
```

## Fase 2

Random Forest.

## Fase 3

LightGBM.

## Fase 4

LightGBM + Quantile Regression.

Resultado:

```text
P10 = 23.800 €
P50 = 25.000 €
P90 = 26.400 €
```

Esto permite representar incertidumbre.

```text
Expected price: 25.000 €
Likely range: 23.800–26.400 €
Confidence: 87%
```

---

# 18. Features del modelo

## Vehículo

- marca
- modelo
- generación
- variante
- año
- mes de matriculación
- kilómetros
- combustible
- cilindrada
- potencia
- transmisión
- tracción
- carrocería
- CO₂

## Equipamiento

- M Sport
- AMG
- S-Line
- quattro
- xDrive
- techo solar
- cuero
- HUD
- cámara
- ACC
- Matrix LED

## Mercado

- país
- ciudad
- distancia a grandes ciudades
- precio medio
- densidad de oferta
- temporada

## Anuncio

- particular/dealer
- antigüedad
- número de modificaciones
- precio
- reducciones
- número/calidad de fotografías
- descripción

---

# 19. Prevención de Data Leakage

El entrenamiento debe respetar la información disponible en el momento de la predicción.

Incorrecto:

```text
01/01
Anuncio publicado

15/01
Anuncio desaparece
```

No se debe utilizar información del 15/01 para generar una predicción que supuestamente se habría realizado el 01/01.

Correcto:

```text
01/01
   ↓
datos disponibles
   ↓
predicción
   ↓
resultado observado posteriormente
```

Los datasets de entrenamiento deben construirse temporalmente.

---

# 20. Import Cost Engine

El motor recibe los datos necesarios:

```json
{
  "country_origin": "DE",
  "destination": "ES",
  "purchase_price": 18500,
  "first_registration": "2020-07",
  "co2": 121,
  "fuel": "diesel",
  "engine_cc": 1995,
  "vehicle_type": "passenger_car"
}
```

Y devuelve un desglose:

```json
{
  "transport": 900,
  "registration_tax": 0,
  "itv": 120,
  "documentation": 150,
  "registration_fee": 100,
  "gestoria": 200,
  "other": 100,
  "total": 1570
}
```

Los valores reales deben calcularse mediante reglas configurables y actualizables.

Nunca:

```python
registration_tax = 500
```

Mejor:

```python
registration_tax = calculate_registration_tax(
    taxable_value,
    co2,
    region,
    vehicle_age
)
```

---

# 21. Reglas fiscales

Las reglas deben estar versionadas.

```text
TaxRules
├── Spain
│   ├── 2026
│   ├── 2027
│   └── ...
├── Germany
├── France
└── Poland
```

El sistema debe poder actualizar reglas sin modificar el código principal del Deal Engine.

---

# 22. Variables fiscales y comerciales

La calculadora debe diferenciar:

```text
Buyer
├── Private
└── Company

Seller
├── Private
└── Dealer
```

Además:

```text
VAT
├── Included
├── Excluded
└── Special margin regime
```

Y determinar si el vehículo es nuevo/usado a efectos fiscales cuando corresponda.

---

# 23. Deal Engine

La oportunidad debe calcularse sobre el coste total.

```text
Expected Spanish Sale Price
-
Purchase Price
-
Transport
-
Taxes
-
ITV
-
Registration
-
Documentation
-
Repairs
-
Preparation
-
Selling Costs
-
Financial Costs
=
Expected Profit
```

Ejemplo:

```text
Venta estimada                  27.000 €
Compra                         -18.000 €
Transporte                        -900 €
Impuestos                         -650 €
ITV/documentación                 -350 €
Reparaciones                      -700 €
Preparación                       -300 €
Financiación                      -250 €
----------------------------------------
Beneficio esperado               5.850 €
```

---

# 24. ROI

```text
ROI = Expected Profit / Total Invested Capital
```

Ejemplo:

```text
Coste total = 21.470 €
Beneficio = 4.530 €

ROI = 21.1%
```

---

# 25. Risk Engine

Una oferta barata no necesariamente es una buena oportunidad.

El sistema debe detectar:

```text
PRICE ANOMALY
VAT RISK
ACCIDENT RISK
MILEAGE RISK
DOCUMENTATION RISK
SELLER RISK
MODEL UNCERTAINTY
```

También puede analizar:

- descripción
- fotografías
- equipamiento
- idioma
- palabras sospechosas
- inconsistencias entre campos

Ejemplos de términos relevantes:

```text
Unfallfrei
Unfallwagen
Motorschaden
Export
Nur Gewerbe
Vollausstattung
```

---

# 26. Deal Score

Propuesta inicial:

```text
35% → margen
20% → confianza de valoración
15% → liquidez
10% → calidad del vehículo
10% → facilidad de importación
10% → riesgo
```

Resultado:

```text
Deal Score: 91/100
Confidence: 87%
Risk Score: 17/100
```

No debe comunicar una ganancia como certeza.

Mejor:

```text
Expected profit: 5.000 €
Likely range: 3.700–6.100 €
Confidence: 87%
```

---

# 27. Liquidez

La aplicación debe estimar cuánto tiempo puede tardar en venderse un vehículo.

Features:

```text
days_on_market
price_reductions
number_of_similar_listings
market_demand
historical_disappearance_rate
```

Ejemplo:

```text
BMW 320d

Precio inicial: 25.900 €
Precio actual: 22.900 €
Reducción: 3.000 €
Días anunciado: 43
```

Esta información puede alimentar tanto el Price Model como el Deal Score.

---

# 28. Current Deal Pipeline

Cuando aparece un anuncio nuevo:

```text
NEW LISTING
     ↓
Normalize
     ↓
Vehicle Matching
     ↓
Validate
     ↓
Current Market Price
     ↓
Spanish Price Prediction
     ↓
Import Cost
     ↓
Risk Analysis
     ↓
Expected Profit
     ↓
ROI
     ↓
Deal Score
     ↓
Dashboard
```

---

# 29. API

## Listings

```http
GET /api/v1/listings
GET /api/v1/listings/{id}
GET /api/v1/listings/active
```

Filtros:

```text
brand
model
country
price_min
price_max
mileage_max
year_min
fuel
transmission
seller_type
deal_score_min
roi_min
```

## Deals

```http
GET /api/v1/deals
GET /api/v1/deals/{id}
```

## Vehicles

```http
GET /api/v1/vehicles/{id}
GET /api/v1/vehicles/{id}/market
GET /api/v1/vehicles/{id}/history
```

## Cost calculation

```http
POST /api/v1/import/calculate
```

## Scraping

Internamente:

```http
POST /internal/scrapers/mobile-de
POST /internal/scrapers/autoscout
```

Estos endpoints no deben exponerse públicamente sin autenticación.

---

# 30. Jobs

Celery gestionará tareas como:

```text
scrape_mobile_de
scrape_autoscout
scrape_otomoto
scrape_coches_net

normalize_listing
update_listing_status
calculate_market_prices
calculate_deals
train_price_model
```

Ejemplo:

```text
Cada 15 min
    mobile.de

Cada 30 min
    AutoScout24

Cada 60 min
    Otomoto

Cada 6 h
    coches.net

Diariamente
    market analytics

Semanalmente
    model retraining
```

Los intervalos deben configurarse según la fuente y sus condiciones de uso.

---

# 31. Redis

Redis tendrá varias funciones:

```text
Celery broker
Cache
Locks
Rate limiting
Temporary job state
```

Ejemplo de lock:

```text
scraper:mobile_de:running
```

Esto evita ejecutar dos scrapers de la misma fuente simultáneamente.

---

# 32. PostgreSQL

PostgreSQL será la fuente principal de verdad.

Debe contener:

```text
vehicles
vehicle_variants
listings
listing_snapshots
listing_events
sellers
sources
countries
locations
equipment
tax_rules
transport_rates
deal_scores
price_predictions
```

---

# 33. PostGIS

PostGIS se utilizará para localización.

Ejemplo:

```text
Vehicle
Berlin, Germany
       ↓
distance
       ↓
Madrid, Spain
       ↓
Transport estimation
```

Esto permitirá posteriormente construir estimaciones de transporte por distancia y región.

---

# 34. ClickHouse

No es necesario inicialmente.

Se introduce cuando el histórico crezca considerablemente.

PostgreSQL:

```text
usuarios
vehículos
anuncios activos
configuración
reglas
```

ClickHouse:

```text
millones de snapshots
series temporales
histórico de precios
analytics
datasets ML
```

---

# 35. Frontend

La pantalla principal debe centrarse en oportunidades actuales.

Ejemplo conceptual:

```text
┌─────────────────────────────────────────────┐
│ DEAL RADAR                                  │
├─────────────────────────────────────────────┤
│                                             │
│ BMW 320d M Sport xDrive                     │
│ 2020 · 87.000 km · Diesel · Automático      │
│                                             │
│ 🇩🇪 Alemania        🇪🇸 España              │
│ 18.490 €            25.200 €               │
│                                             │
│ Importación:      1.650 €                  │
│ Coste total:     20.140 €                  │
│ Venta estimada:  25.200 €                  │
│                                             │
│ Beneficio:        5.060 €                  │
│ ROI:                 25.1%                 │
│                                             │
│ Deal Score:       91/100                   │
│ Risk Score:       17/100                   │
│                                             │
│ [VER ANUNCIO] [ANALIZAR]                   │
└─────────────────────────────────────────────┘
```

---

# 36. Dashboard futuro

Secciones:

```text
Dashboard
├── 🔥 Best Deals
├── 🆕 Nuevos
├── 📉 Price Drops
├── 🇩🇪 Alemania
├── 🇵🇱 Polonia
├── 🇫🇷 Francia
├── 🇪🇸 Mercado español
├── 📊 Market Analytics
├── 🚨 Alerts
└── ⚙ Settings
```

---

# 37. Alertas

Cuando una oferta supera determinados criterios:

```text
Expected Profit > 4.000 €
ROI > 20%
Deal Score > 85
Risk Score < 30
```

se genera:

```text
🔥 New Deal

BMW 330d
Germany → Spain

Purchase: 21.900 €
Expected Spain: 29.400 €
Total landed: 24.100 €

Expected profit: 5.300 €
ROI: 22%

Deal Score: 94/100
```

Canales futuros:

- Web
- Email
- Telegram
- Discord
- Push notifications

---

# 38. Seguridad

Variables sensibles fuera del código:

```text
.env
```

Ejemplo:

```env
DATABASE_URL=
REDIS_URL=

SECRET_KEY=

R2_ENDPOINT=
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET=

SCRAPER_PROXY=
```

Nunca subir `.env` a Git.

Utilizar:

```text
.env.example
```

---

# 39. Observabilidad

Cada scraper debería registrar:

```text
started_at
finished_at
source
pages_requested
listings_found
listings_new
listings_updated
parse_errors
network_errors
blocked_requests
duration
```

Métricas importantes:

```text
scraper_success_rate
parse_success_rate
listings_per_run
new_listings
removed_listings
average_latency
database_insert_rate
```

---

# 40. Testing

## Unit tests

- normalización
- parsers
- impuestos
- transporte
- Deal Score
- ROI
- matching

## Integration tests

```text
scraper
 ↓
parser
 ↓
database
```

## ML tests

- train/test temporal
- MAE
- RMSE
- MAPE
- quantile coverage

Especialmente importante:

```text
NO RANDOM TRAIN/TEST SPLIT
```

cuando produzca leakage temporal.

Preferir:

```text
TRAIN → pasado
VALIDATION → periodo posterior
TEST → periodo aún más reciente
```

---

# 41. MVP

El MVP no debe intentar cubrir toda Europa.

## Países

### Alemania

- mobile.de
- AutoScout24

### España

- coches.net
- AutoScout24 España

### Opcional

Polonia:

- Otomoto

---

# 42. MVP funcional

La primera versión debería ser capaz de:

```text
1. Scrapear ofertas
2. Guardarlas
3. Detectar nuevas ofertas
4. Actualizar snapshots
5. Detectar desapariciones
6. Normalizar vehículos
7. Comparar mercado europeo/español
8. Calcular costes básicos
9. Calcular margen
10. Mostrar oportunidades activas
```

Todavía NO es necesario:

- deep learning
- computer vision avanzado
- ClickHouse
- Kubernetes
- arquitectura distribuida compleja
- 10 países
- LLM sofisticado

---

# 43. Orden de implementación

## Fase 0 — Infrastructure

```text
Git
Docker
PostgreSQL
Redis
FastAPI
Next.js
```

## Fase 1 — First scraper

Elegir una única fuente.

```text
mobile.de
```

Objetivo:

```text
Scrape
 ↓
Normalize
 ↓
PostgreSQL
```

## Fase 2 — Historical system

Implementar:

```text
listings
listing_snapshots
listing_events
```

Y comprobar correctamente:

```text
new
active
stale
removed
reappeared
```

## Fase 3 — Second market

Añadir:

```text
coches.net
```

Ahora comienza la comparación:

```text
Germany → Spain
```

## Fase 4 — Vehicle matching

Resolver:

```text
same vehicle variant
```

entre fuentes.

## Fase 5 — Market valuation

Primero:

```text
median
percentiles
comparables
```

Después ML.

## Fase 6 — Import Cost Engine

Añadir:

```text
transport
tax
ITV
registration
documentation
gestoria
other costs
```

## Fase 7 — Deal Engine

Añadir:

```text
expected profit
ROI
risk
confidence
Deal Score
```

## Fase 8 — ML

```text
baseline
 ↓
Random Forest
 ↓
LightGBM
 ↓
Quantile Regression
```

## Fase 9 — Alerts

## Fase 10 — More countries

```text
DE
PL
FR
IT
BE
NL
AT
...
```

---

# 44. Primer milestone técnico

Antes de construir el ML, el sistema debería poder ejecutar:

```text
mobile.de
    ↓
50.000 listings
    ↓
PostgreSQL
    ↓
normalización
    ↓
listing_snapshots
    ↓
status tracking
```

Y posteriormente:

```text
coches.net
    ↓
mercado español
```

El primer objetivo importante no es "tener IA".

Es conseguir un dataset limpio, histórico y temporalmente consistente.

---

# 45. Objetivo de dataset

Objetivo inicial:

```text
100k–500k listings normalizados
```

Posteriormente:

```text
500k listings
     ↓
2M+ snapshots
     ↓
200k+ vehicle variants
     ↓
Spanish market valuations
     ↓
Import cost calculations
     ↓
Deal Engine
```

---

# 46. Ventaja competitiva

La ventaja competitiva no debería ser el scraper.

El núcleo defensible es:

```text
DATA
 ↓
NORMALIZATION
 ↓
VEHICLE MATCHING
 ↓
PRICE MODEL
 ↓
IMPORT COST ENGINE
 ↓
RISK ENGINE
 ↓
DEAL SCORE
```

Cuanto más histórico acumule el sistema:

```text
más datos
 ↓
mejor matching
 ↓
mejores comparables
 ↓
mejor valoración
 ↓
mejor Deal Score
 ↓
mejores oportunidades
```

Esto genera un ciclo de mejora continua.

---

# 47. Principios arquitectónicos

1. **No borrar histórico.**
2. **No mezclar anuncios con vehículos.**
3. **No mezclar live data con historical data.**
4. **No depender de una única fuente.**
5. **Cada scraper debe ser independiente.**
6. **Conservar raw data siempre que sea posible.**
7. **Toda transformación importante debe ser reproducible.**
8. **Las reglas fiscales deben estar versionadas.**
9. **Los modelos deben entrenarse respetando el tiempo.**
10. **No utilizar un LLM como modelo principal de precio.**
11. **Toda predicción debe tener una medida de incertidumbre.**
12. **No considerar automáticamente que un anuncio desaparecido fue vendido.**
13. **La infraestructura debe escalar sólo cuando el volumen lo requiera.**
14. **Cumplir las condiciones y licencias de cada fuente de datos.**

---

# 48. Resultado final esperado

El sistema completo debería transformar:

```text
Anuncio europeo
```

en:

```text
┌──────────────────────────────────────────┐
│ VEHICLE                                  │
│ BMW 320d G20                             │
│ 2020 · 87.000 km · Diesel · Auto         │
├──────────────────────────────────────────┤
│ PURCHASE                                 │
│ Germany                                  │
│ 18.490 €                                 │
├──────────────────────────────────────────┤
│ MARKET                                   │
│ Spain expected: 25.200 €                 │
│ Confidence: 87%                          │
├──────────────────────────────────────────┤
│ IMPORT                                   │
│ Transport: 900 €                         │
│ Taxes: 450 €                             │
│ Documentation: 300 €                    │
│ Total import: 1.650 €                   │
├──────────────────────────────────────────┤
│ PROFIT                                   │
│ Total cost: 20.140 €                    │
│ Expected sale: 25.200 €                 │
│ Expected profit: 5.060 €                │
│ ROI: 25.1%                               │
├──────────────────────────────────────────┤
│ RISK                                     │
│ Risk Score: 17/100                      │
├──────────────────────────────────────────┤
│ DEAL                                     │
│ Deal Score: 91/100                      │
│                                          │
│ 🔥 HIGH OPPORTUNITY                      │
└──────────────────────────────────────────┘
```

El objetivo final no es construir otro buscador de coches.

Es construir un **sistema de análisis de vehicle arbitrage Europa → España**, capaz de descubrir oportunidades que sean difíciles de detectar manualmente.
