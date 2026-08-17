# 🚗 Car Deal Radar — Europa → España

Sistema de análisis de oportunidades para detectar coches potencialmente rentables de importar desde Europa y revender en España.

La aplicación combina **scraping/recolección de datos, normalización de vehículos, histórico de precios, valoración de mercado, cálculo de costes de importación, análisis de riesgo y machine learning** para encontrar oportunidades reales de compra.

---

## 📌 Idea del proyecto

El objetivo no es crear otro buscador de coches.

El objetivo es construir un **radar de oportunidades de importación y reventa**:

```text
Fuentes europeas
      ↓
Scraping / APIs
      ↓
Normalización
      ↓
Identificación del vehículo
      ↓
Histórico de precios
      ↓
Valoración mercado europeo
      ↓
Valoración mercado español
      ↓
Costes de importación
      ↓
Riesgo
      ↓
Beneficio esperado
      ↓
Deal Score
      ↓
Dashboard
```

Ejemplo:

```text
BMW 320d 2020

Compra Alemania:          18.500 €
Transporte:                  900 €
Impuestos:                 1.200 €
ITV/documentación:           400 €
-----------------------------------
Coste total:              21.000 €

Valor estimado España:    26.000 €

Beneficio estimado:        5.000 €
ROI:                         23.8 %
```

La aplicación debe determinar si una oferta es realmente interesante después de tener en cuenta **todos los costes**, no simplemente si el precio extranjero es inferior al español.

---

# 🎯 Objetivos

## Objetivo principal

Encontrar automáticamente vehículos que tengan una elevada probabilidad de generar beneficio al ser importados a España.

## Objetivos secundarios

- Crear una base histórica de anuncios.
- Conocer la evolución de precios.
- Comparar mercados europeos.
- Estimar el valor real de un vehículo en España.
- Calcular automáticamente los costes de importación.
- Detectar anuncios anómalos o de riesgo.
- Priorizar oportunidades mediante un Deal Score.
- Entrenar modelos de machine learning con datos históricos.
- Crear alertas cuando aparezca una oportunidad especialmente buena.

---

# 🌍 Fuentes de datos

## MVP

### Alemania

- mobile.de
- AutoScout24

### España

- coches.net
- AutoScout24 España

### Segunda fase

- Otomoto — Polonia

### Futuro

- Francia
- Italia
- Bélgica
- Países Bajos
- Austria
- otros mercados europeos

> Antes de utilizar comercialmente una fuente deben revisarse sus APIs, licencias, términos de uso, robots.txt, límites de frecuencia y condiciones de almacenamiento/redistribución de datos.

Cuando exista una API o feed autorizado, debe priorizarse frente al scraping directo.

---

# 🧠 Concepto fundamental: histórico vs. ofertas actuales

El sistema debe almacenar **todo el histórico**, pero el usuario debe ver únicamente las ofertas disponibles en el momento actual.

La arquitectura separa:

```text
HISTORICAL DATA
       │
       ├── snapshots
       ├── price changes
       ├── removed listings
       ├── historical prices
       └── market statistics

CURRENT DATA
       │
       └── ACTIVE listings
```

## Histórico

Se utiliza para:

- entrenar modelos;
- analizar precios;
- estudiar evolución del mercado;
- calcular días en mercado;
- detectar reducciones de precio;
- estudiar liquidez;
- construir datasets de ML.

## Live

Se utiliza para:

- encontrar oportunidades;
- generar Deal Scores;
- mostrar ofertas actuales;
- enviar alertas.

Por tanto:

```sql
SELECT *
FROM listings
WHERE status = 'ACTIVE';
```

es la consulta conceptual del dashboard de oportunidades actuales.

---

# 🏗️ Arquitectura general

```text
                         ┌──────────────────────┐
                         │      SOURCES         │
                         │                      │
                         │ mobile.de            │
                         │ AutoScout24           │
                         │ Otomoto               │
                         │ coches.net             │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       SCRAPERS       │
                         │      Playwright       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       RAW DATA       │
                         │     HTML / JSON      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    NORMALIZATION     │
                         └──────────┬───────────┘
                                    │
                       ┌────────────┴────────────┐
                       ▼                         ▼
                ┌──────────────┐          ┌──────────────┐
                │   VEHICLES   │          │   LISTINGS   │
                └──────┬───────┘          └──────┬───────┘
                       │                         │
                       │                         ▼
                       │                 ┌────────────────┐
                       │                 │ LISTING EVENTS │
                       │                 └───────┬────────┘
                       │                         │
                       │                         ▼
                       │                 ┌────────────────┐
                       │                 │   SNAPSHOTS    │
                       │                 └───────┬────────┘
                       │                         │
                       └────────────┬────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │  HISTORICAL DATA     │
                         │     / ANALYTICS      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                  ┌─────────────┐       ┌──────────────┐
                  │ PRICE MODEL │       │   ANALYTICS  │
                  └──────┬──────┘       └──────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ IMPORT COST  │
                  │    ENGINE    │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ RISK ENGINE  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ DEAL ENGINE  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   FastAPI    │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │    Next.js   │
                  └──────────────┘
```

---

# 🛠️ Stack tecnológico

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

## Jobs

- Celery
- Redis

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
- Cloudflare R2 (free tier) para almacenamiento raw

## Futuro

- ClickHouse
- OpenSearch
- Prometheus
- Grafana
- Sentry

No se recomienda introducir toda esta infraestructura desde el principio.

---

# 📂 Estructura del proyecto

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
│   └── types/
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

# 🚗 Modelo de datos

La arquitectura debe distinguir:

```text
VEHICLE
   │
   └── LISTING
          │
          ├── LISTING_EVENT
          │
          └── LISTING_SNAPSHOT
```

Esto permite que un mismo vehículo pueda tener varios anuncios a lo largo del tiempo.

---

## `vehicles`

Representa la identidad normalizada del vehículo.

Ejemplo:

```text
BMW
└── Serie 3
    └── G20
        └── 320d
            └── xDrive
                └── M Sport
```

Campos principales:

```text
id
brand
model
generation
variant
year
registration_date
fuel
transmission
drivetrain
power_kw
engine_cc
co2_g_km
body_type
```

---

## `listings`

Representa un anuncio concreto de una fuente.

Campos:

```text
id
vehicle_id
source
source_listing_id
url
seller_type
country
first_seen_at
last_seen_at
status
created_at
updated_at
```

Clave única:

```text
source + source_listing_id
```

Ejemplo:

```text
mobile.de + 123456789
```

identifica un anuncio concreto.

---

## `listing_snapshots`

Guarda el estado del anuncio en cada scraping.

Ejemplo:

```text
01/08 → 24.900 €
05/08 → 23.900 €
11/08 → 22.900 €
```

Nunca se deben sobrescribir snapshots anteriores.

Campos:

```text
listing_id
scraped_at
price
mileage
title
description
seller_type
location
raw_data
```

---

## `listing_events`

Registra cambios importantes:

```text
LISTED
PRICE_CHANGED
DESCRIPTION_CHANGED
MILEAGE_CHANGED
STATUS_CHANGED
REMOVED
REAPPEARED
```

Ejemplo:

```text
01/08 → LISTED → 24.900 €
05/08 → PRICE_CHANGED → 23.900 €
11/08 → PRICE_CHANGED → 22.900 €
15/08 → REMOVED
```

---

# 🔴 Estados de un anuncio

Se utilizarán inicialmente:

```text
ACTIVE
STALE
REMOVED
SOLD
```

Importante:

```text
REMOVED ≠ SOLD
```

Un anuncio puede desaparecer porque:

- se vendió;
- el vendedor lo retiró;
- se reservó;
- cambió de portal;
- se republicó;
- cambió su ID;
- el scraper falló.

---

# ⏱️ Detección de disponibilidad

No se debe marcar inmediatamente como eliminado un anuncio que no aparezca en un scraping.

Ejemplo:

```text
08:00 → aparece
10:00 → aparece
12:00 → no aparece
14:00 → no aparece
16:00 → no aparece
```

La primera ausencia puede ser un error de scraping.

Se utiliza:

```text
last_seen_at
```

y una política configurable:

```text
> 6 horas sin aparecer
        ↓
      STALE

> 48 horas sin aparecer
        ↓
     REMOVED
```

Los valores deben ser configurables por fuente.

---

# 🕷️ Sistema de scraping

Cada fuente tendrá su propio scraper.

```text
scrapers/
├── base/
│
├── mobile_de/
│   ├── scraper.py
│   ├── parser.py
│   └── mapper.py
│
├── autoscout/
│   ├── scraper.py
│   ├── parser.py
│   └── mapper.py
│
├── otomoto/
│   ├── scraper.py
│   ├── parser.py
│   └── mapper.py
│
└── coches_net/
    ├── scraper.py
    ├── parser.py
    └── mapper.py
```

Todos deben producir:

```text
NormalizedListing
```

Así, si una fuente cambia su HTML, solamente hay que adaptar ese scraper.

---

# 📦 `NormalizedListing`

Ejemplo conceptual:

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

Pipeline:

```text
SOURCE
 ↓
SCRAPER
 ↓
PARSER
 ↓
MAPPER
 ↓
NormalizedListing
 ↓
VALIDATION
 ↓
DATABASE
```

---

# 🧹 Normalización y Vehicle Matching

Este es uno de los problemas más importantes del proyecto.

Ejemplo:

```text
mobile.de:
BMW 320 d xDrive M Sport

AutoScout:
BMW 320d xDrive M Sportpaket

coches.net:
BMW Serie 3 320d xDrive M Sport Auto
```

El sistema debe entender que pertenecen a la misma variante.

## Estrategia inicial

1. Normalización de texto.
2. Diccionarios.
3. Reglas.
4. Fuzzy matching.
5. Campos técnicos.
6. VIN cuando exista.

## Futuro

- embeddings;
- modelos específicos de matching;
- LLM para extracción estructurada.

El LLM **no será el modelo principal de valoración de precios**.

---

# 📊 Data Quality

Cada dato importante debería conservar:

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

Si existen datos contradictorios, deben conservarse sus fuentes.

---

# 💰 Sistema de valoración

La aplicación tendrá dos modelos principales:

```text
European Price
Spanish Price
```

Conceptualmente:

```text
P_europe = f(vehicle, country, market)

P_spain = f(vehicle, Spanish market)
```

El objetivo es estimar el valor de mercado de un vehículo concreto.

No basta con:

```text
precio medio de anuncios
```

---

# 🤖 Machine Learning

## Fase 1 — Baseline

- mediana;
- percentiles;
- vehículos comparables.

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

En lugar de:

```text
Precio = 25.000 €
```

podemos indicar:

```text
Precio esperado: 25.000 €
Rango probable: 23.800–26.400 €
Confianza: 87 %
```

---

# 🧮 Features del modelo

## Vehículo

- marca
- modelo
- generación
- versión
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
- estacionalidad

## Anuncio

- particular/dealer
- antigüedad
- precio
- reducciones de precio
- número de fotos
- calidad de fotos
- descripción

---

# ⚠️ Prevención de Data Leakage

Los modelos deben entrenarse únicamente con información que habría estado disponible en el momento de la predicción.

Incorrecto:

```text
01/01
Anuncio publicado
20.000 €

15/01
Anuncio desaparece
```

No se puede usar información del 15/01 para generar una predicción supuestamente realizada el 01/01.

Correcto:

```text
01/01
 ↓
datos disponibles
 ↓
predicción
 ↓
resultado posterior
```

El dataset debe construirse temporalmente.

Preferentemente:

```text
TRAIN → pasado
VALIDATION → periodo posterior
TEST → periodo aún más reciente
```

---

# 🇪🇸 Import Cost Engine

Este módulo calcula el coste completo de poner un vehículo en España.

Entrada:

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

Salida conceptual:

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

Los valores deben ser calculados mediante reglas configurables.

No:

```python
registration_tax = 500
```

Sí:

```python
registration_tax = calculate_registration_tax(
    taxable_value,
    co2,
    region,
    vehicle_age
)
```

---

# 🧾 Fiscalidad

La calculadora debe diferenciar:

```text
COMPRADOR
├── Particular
└── Empresa

VENDEDOR
├── Particular
└── Profesional
```

Y:

```text
IVA
├── Incluido
├── No incluido
└── Régimen especial/margen
```

También debe determinar correctamente el tratamiento fiscal del vehículo según su antigüedad, kilometraje y operación.

Las reglas fiscales deben estar versionadas:

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

---

# 🚚 Transporte

El coste de transporte dependerá de:

```text
país origen
ubicación
destino
distancia
tipo de transporte
tipo de vehículo
```

PostGIS permitirá calcular distancias geográficas.

Ejemplo:

```text
Berlin
 ↓
1.870 km
 ↓
Madrid
 ↓
Transport estimation
```

---

# 💵 Deal Engine

El cálculo correcto es:

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
Venta estimada                 27.000 €
Compra                        -18.000 €
Transporte                       -900 €
Impuestos                        -650 €
ITV/documentación                -350 €
Reparaciones                     -700 €
Preparación                      -300 €
Coste financiero                -250 €
---------------------------------------
Beneficio esperado              5.850 €
```

---

# 📈 ROI

```text
ROI = Expected Profit / Total Invested Capital
```

Ejemplo:

```text
Coste total = 21.470 €
Beneficio = 4.530 €

ROI = 21,1 %
```

---

# 🚨 Risk Engine

Un precio extremadamente bajo no significa automáticamente que sea una buena oportunidad.

Se analizarán:

```text
PRICE ANOMALY
VAT RISK
ACCIDENT RISK
MILEAGE RISK
DOCUMENTATION RISK
SELLER RISK
MODEL UNCERTAINTY
```

También pueden analizarse descripciones.

Ejemplos de términos relevantes:

```text
Unfallfrei
Unfallwagen
Motorschaden
Export
Nur Gewerbe
Vollausstattung
```

En fases futuras:

- análisis de fotografías;
- detección de daños;
- clasificación del estado;
- análisis avanzado de descripciones.

---

# ⭐ Deal Score

Propuesta inicial:

```text
35 % → margen
20 % → confianza del precio
15 % → liquidez
10 % → calidad del vehículo
10 % → facilidad de importación
10 % → riesgo
```

Ejemplo:

```text
Deal Score: 91/100
Confidence: 87 %
Risk Score: 17/100
```

Nunca debe presentarse una predicción como una garantía de beneficio.

Mejor:

```text
Beneficio esperado: 5.000 €
Intervalo probable: 3.700–6.100 €
Confianza: 87 %
```

---

# 📦 Liquidez

Se debe estimar cuánto puede tardar un vehículo en venderse.

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

Esto puede alimentar el Deal Score.

---

# 🔄 Pipeline de una oportunidad

Cuando aparece una oferta:

```text
NEW LISTING
     ↓
NORMALIZE
     ↓
VEHICLE MATCHING
     ↓
VALIDATE
     ↓
EUROPEAN MARKET PRICE
     ↓
SPANISH PRICE
     ↓
IMPORT COST
     ↓
RISK ANALYSIS
     ↓
EXPECTED PROFIT
     ↓
ROI
     ↓
DEAL SCORE
     ↓
DASHBOARD
```

---

# 🖥️ Dashboard

La pantalla principal mostrará únicamente oportunidades actuales.

Ejemplo:

```text
┌──────────────────────────────────────────┐
│ 🚗 DEAL RADAR                            │
├──────────────────────────────────────────┤
│ BMW 320d M Sport xDrive                  │
│ 2020 · 87.000 km · Diesel · Automático   │
│                                          │
│ 🇩🇪 Alemania       🇪🇸 España             │
│ 18.490 €           25.200 €              │
│                                          │
│ Importación:       1.650 €               │
│ Coste total:      20.140 €               │
│ Venta estimada:   25.200 €               │
│                                          │
│ Beneficio:         5.060 €               │
│ ROI:                  25,1 %              │
│                                          │
│ Deal Score:          91/100              │
│ Risk Score:          17/100              │
│                                          │
│ [VER ANUNCIO] [ANALIZAR]                 │
└──────────────────────────────────────────┘
```

---

# 🔌 API

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

## Costes

```http
POST /api/v1/import/calculate
```

---

# ⚙️ Jobs y scraping programado

FastAPI no debe quedarse esperando mientras un scraper trabaja.

Incorrecto:

```text
GET /scrape
 ↓
esperar 45 minutos
```

Correcto:

```text
FastAPI
 ↓
Redis
 ↓
Celery
 ↓
Scraper Worker
```

Tareas:

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

Ejemplo inicial:

```text
Cada 15 min → mobile.de
Cada 30 min → AutoScout24
Cada 60 min → Otomoto
Cada 6 h    → mercado español
```

Los intervalos deben adaptarse a las condiciones de cada fuente.

---

# 🗄️ PostgreSQL

Será la fuente principal de verdad.

Entidades iniciales:

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
price_predictions
deal_scores
```

---

# 📊 ClickHouse

No es necesario para el MVP.

Se añadirá cuando el histórico sea suficientemente grande.

## PostgreSQL

```text
usuarios
vehículos
ofertas activas
configuración
reglas
```

## ClickHouse

```text
millones de snapshots
histórico de precios
series temporales
analytics
datasets ML
```

---

# 🔴 Redis

Funciones:

```text
Celery broker
Cache
Locks
Rate limiting
Temporary job state
```

Ejemplo:

```text
scraper:mobile_de:running
```

Evita ejecutar dos procesos simultáneos de la misma fuente.

---

# ☁️ Infraestructura inicial

Para comenzar:

```text
Oracle Cloud Always Free
 │
 ├── FastAPI
 ├── PostgreSQL
 ├── Redis
 ├── Celery
 └── Scraper workers
```

Posteriormente:

```text
Cloudflare
    ↓
Load Balancer
    ↓
API Servers
    ↓
PostgreSQL
    ↓
Redis
    ↓
Scraper Cluster
    ↓
R2
    ↓
ClickHouse
```

No se debe introducir arquitectura distribuida compleja hasta que el volumen la justifique.

---

# 🔐 Variables de entorno

Crear:

```text
.env
```

a partir de:

```text
.env.example
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

---

# 📡 Observabilidad

Cada scraper debe registrar:

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

Métricas:

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

# 🧪 Testing

## Unit tests

- parsers;
- normalización;
- matching;
- impuestos;
- transporte;
- Deal Score;
- ROI.

## Integration tests

```text
scraper
 ↓
parser
 ↓
database
```

## ML tests

- MAE;
- RMSE;
- MAPE;
- quantile coverage.

El split debe ser temporal:

```text
TRAIN → pasado
VALIDATION → futuro cercano
TEST → futuro posterior
```

No utilizar un split aleatorio si introduce información futura en el entrenamiento.

---

# 🚀 Roadmap

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

Comenzar con una sola fuente:

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

Comprobar:

```text
new
active
stale
removed
reappeared
```

## Fase 3 — Spanish market

Añadir:

```text
coches.net
```

Ahora:

```text
Germany → Spain
```

## Fase 4 — Vehicle matching

Resolver equivalencias entre fuentes.

## Fase 5 — Market valuation

Primero:

```text
median
percentiles
comparables
```

Después:

```text
ML
```

## Fase 6 — Import Cost Engine

Añadir:

```text
transport
tax
ITV
registration
documentation
gestoria
other
```

## Fase 7 — Deal Engine

Añadir:

```text
margin
ROI
risk
confidence
Deal Score
```

## Fase 8 — Machine Learning

```text
Baseline
 ↓
Random Forest
 ↓
LightGBM
 ↓
Quantile Regression
```

## Fase 9 — Alertas

```text
New Deal
Price Drop
High ROI
Low Risk
```

## Fase 10 — Europa

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

# 🎯 MVP

El MVP debe centrarse en:

```text
Alemania → España
```

con:

```text
mobile.de
AutoScout24
coches.net
```

Debe ser capaz de:

1. Recopilar anuncios.
2. Guardarlos.
3. Detectar nuevos anuncios.
4. Actualizar snapshots.
5. Detectar desapariciones.
6. Normalizar vehículos.
7. Comparar mercados.
8. Calcular costes.
9. Calcular margen.
10. Mostrar oportunidades activas.

No es necesario inicialmente:

- deep learning;
- computer vision;
- ClickHouse;
- Kubernetes;
- 10 países;
- LLM avanzado.

---

# 📈 Objetivo de dataset

Primer objetivo:

```text
100.000–500.000 listings normalizados
```

Objetivo posterior:

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
DEAL ENGINE
```

El activo principal acaba siendo el dataset histórico.

---

# 💡 Ventaja competitiva

El scraping por sí solo no es una ventaja competitiva fuerte.

El núcleo diferencial es:

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

El ciclo de mejora esperado:

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
   ↓
más datos
```

---

# 📏 Métricas principales

## Mercado

- número de anuncios activos;
- precio medio;
- mediana;
- P10/P90;
- días en mercado;
- reducciones de precio.

## Scraping

- listings encontrados;
- listings nuevos;
- listings actualizados;
- listings eliminados;
- errores;
- cobertura.

## ML

- MAE;
- RMSE;
- MAPE;
- cobertura de intervalos;
- error por marca/modelo/mercado.

## Negocio

- beneficio esperado;
- ROI;
- Deal Score;
- Risk Score;
- liquidez;
- probabilidad de superar un beneficio mínimo.

---

# 🧭 Primer milestone técnico

Antes de construir el ML, el sistema debe poder hacer:

```text
mobile.de
    ↓
datos
    ↓
PostgreSQL
    ↓
normalización
    ↓
listing_snapshots
    ↓
status tracking
```

Después:

```text
coches.net
    ↓
mercado español
```

El primer objetivo **no es tener IA**.

El primer objetivo es conseguir un dataset:

- limpio;
- histórico;
- normalizado;
- temporalmente consistente;
- con anuncios activos correctamente identificados.

---

# ⚠️ Principios arquitectónicos

1. No borrar histórico.
2. No mezclar vehículos con anuncios.
3. No mezclar datos live con históricos.
4. No depender de una única fuente.
5. Cada scraper debe ser independiente.
6. Conservar raw data siempre que sea posible.
7. Hacer las transformaciones reproducibles.
8. Versionar las reglas fiscales.
9. Entrenar modelos respetando el tiempo.
10. No utilizar un LLM como modelo principal de precio.
11. Toda predicción debe tener incertidumbre.
12. `REMOVED` no significa automáticamente `SOLD`.
13. Escalar infraestructura únicamente cuando sea necesario.
14. Revisar las condiciones de uso y licencias de cada fuente.

---

# 🏁 Resultado final

El sistema debe transformar un anuncio europeo:

```text
BMW 320d
2020
87.000 km
18.490 €
Alemania
```

en una decisión de inversión:

```text
┌──────────────────────────────────────────┐
│ BMW 320d G20                             │
├──────────────────────────────────────────┤
│ Compra Alemania:        18.490 €         │
│ Importación:             1.650 €         │
│ Coste total:            20.140 €         │
│                                          │
│ Valor España esperado:  25.200 €         │
│ Beneficio esperado:      5.060 €         │
│ ROI:                        25,1 %        │
│                                          │
│ Confidence:                  87 %        │
│ Risk Score:                  17/100      │
│ Deal Score:                  91/100      │
│                                          │
│ 🔥 HIGH OPPORTUNITY                      │
└──────────────────────────────────────────┘
```

El objetivo final es construir un **sistema de vehicle arbitrage Europa → España**, capaz de encontrar oportunidades que serían difíciles de detectar manualmente.

---

## 📚 Documentación relacionada

- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`DATA_MODEL.md`](./docs/DATA_MODEL.md)
- [`SCRAPERS.md`](./docs/SCRAPERS.md)
- [`ML.md`](./docs/ML.md)
- [`IMPORT_COSTS.md`](./docs/IMPORT_COSTS.md)
