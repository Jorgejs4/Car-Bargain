# Scrapers: diagnóstico y guía de implementación

Este documento registra el estado real de cada fuente (verificado en vivo,
agosto 2026) y explica **cómo construir un scraper funcional** de cada página.
Todo scraper entrega el mismo contrato: `NormalizedListing`
(`backend/scrapers/base/models.py`) mediante las interfaces
`BaseParser`/`BaseMapper`/`BaseScraper` (`backend/scrapers/base/interfaces.py`).

Contenido de este documento:

1. [Estado verificado por fuente](#1-estado-verificado-por-fuente)
2. [Patrón común de un scraper](#2-patrón-común-de-un-scraper)
3. [mobile.de](#3-mobilede)
4. [AutoScout24](#4-autoscout24)
5. [coches.net](#5-cochesnet)
6. [Anti-bot y resiliencia](#6-anti-bot-y-resiliencia)
7. [Cómo integrar una fuente nueva](#7-cómo-integrar-una-fuente-nueva)

---

## 1. Estado verificado por fuente

| Fuente | Live | Método de datos | Anti-bot | Estado |
|---|---|---|---|---|
| mobile.de | **403 bloqueado** | `window.__INITIAL_STATE__` (JSON SSR) | Akamai Bot Manager (TLS fingerprinting + challenge JS) | Funciona vía **Wayback** (`wayback.py`); live requiere IP residencial/proxy (`scraper_proxy`) o Playwright |
| AutoScout24.es | **200 OK** | `__NEXT_DATA__` (JSON SSR) | Akamai, pero responde a GET con headers de navegador | **Funcional en vivo** (`scrapers/autoscout24/`) |
| coches.net | **200 OK** (bloqueo intermitente) | `window.__INITIAL_PROPS__` (JSON SSR escapado en string JS) | Página-challenge JS intercalada ("Ups! Parece que algo no va bien...") | **Funcional en vivo** (`scrapers/coches_net/`) con detección del bloqueo |

> **Regla de oro:** nunca se silencian fallos de fetch; un bloqueo (403,
> página-challenge) se propaga como error. Solo se descartan anuncios
> individuales que no mapean bien.

---

## 2. Patrón común de un scraper

Cada fuente vive en `backend/scrapers/<fuente>/` con tres archivos:

```
scrapers/<fuente>/
├── parser.py   # BaseParser: HTML/JSON -> list[dict] (registros raw)
├── mapper.py   # BaseMapper: record dict -> NormalizedListing
├── scraper.py  # BaseScraper: fetch -> parse -> map -> validate
└── __init__.py # re-exporta las clases públicas
```

- **Parser** solo extrae; no traduce. Devuelve dicts crudos.
- **Mapper** traduce al vocabulario canónico del proyecto:
  - `fuel`: `petrol | diesel | electric | hybrid | plug-in-hybrid | lpg | cng | hydrogen`
  - `transmission`: `manual | automatic | semi-automatic | dual-clutch | cvt`
  - `seller_type`: `commercial | dealer | private`
  - Valores desconocidos/ausentes → `None` (nunca inventar señales).
- **Scraper** orquesta páginas y propaga errores de transporte (403/429/5xx).
- Identidad: `source_listing_id` único por fuente.

---

## 3. mobile.de

### Cómo funciona la página

mobile.de es una SPA. La página de búsqueda incrusta el estado SSR en:

```js
window.__INITIAL_STATE__ = {...}
```

Estructura del JSON (verificado contra snapshot Wayback 2025-12):

```
state["search"]["srp"]["data"]["searchResults"]["items"]   # lista de anuncios
state["search"]["srp"]["data"]["searchResults"]["page|numPages|hasNextPage"]
```

Cada anuncio raw tiene `id`, `make`, `model`, `price.grossAmount`,
`relativeUrl`, `contactInfo.typeLocalized`, `attr` (con `cn`, `loc`, `fr`,
`pw`, `ft`, `ml`, `cc`, `tr`, `emiss`) y `previewThumbnails`/`previewImage`.

### Cómo scrapearlo

- URL de búsqueda: `https://suchen.mobile.de/fahrzeuge/search.html`
  con `isSearchRequest=true&scopeId=C&page=N`.
- El host responde **403 a IPs de datacenter** (verificado). Para un live
  funcional:
  1. Configurar `scraper_proxy` en el `.env` con una IP residencial/alojada en
     el país, y `Accept-Language: de-DE`.
  2. O ejecutar con Playwright y leer `window.__INITIAL_STATE__` del DOM.
  3. Fallback offline: `scrapers/mobile_de/wayback.py` (CDX API → snapshot →
     mismo parser/mapper). Ver `scripts/scrape_mobile_de_wayback.py`.
- El `_fetch` reintenta 429/errores de red y propaga el 403.

### Fixtures y tests

- Fixture real: `backend/tests/fixtures/mobile_de/search_page.html` (24 anuncios).
- `backend/tests/scrapers/test_mobile_de.py` y `test_wayback.py`.

---

## 4. AutoScout24

### Cómo funciona la página

AutoScout24 es Next.js. Cada página (SRP y detalle) incrusta todo el estado en:

```html
<script id="__NEXT_DATA__" type="application/json"> {json} </script>
```

Estructura del SRP (verificado en vivo 2026-08):

```
data["props"]["pageProps"]["listings"]         # 20 anuncios por página
data["props"]["pageProps"]["numberOfResults"]  # total
data["props"]["pageProps"]["numberOfPages"]    # páginas (cap @200)
```

Cada anuncio raw:

```json
{
  "id": "17c65c53-...",
  "url": "/anuncios/...-17c65c53-...",
  "images": ["https://prod.pictures.autoscout24.net/..."],
  "price": {"priceRaw": 3890, "priceFormatted": "€ 3.890"},
  "vehicle": {"make": "Citroen", "model": "C4 Cactus", "modelVersionInput": "BlueHDi 100 Feel",
              "transmission": "manual", "fuel": "Diésel", "mileageInKm": "220.957 km"},
  "location": {"countryCode": "ES", "zip": "28914", "city": "Leganés"},
  "seller": {"type": "Dealer", "companyName": "..."},
  "vehicleDetails": [
    {"data": "10/2015", "ariaLabel": "Año"},
    {"data": "73 kW (99 CV)", "iconName": "speedometer", "ariaLabel": "Potencia"},
    ...
  ]
}
```

Nota: el SRP **no expone** año ni potencia de forma directa; se extraen de
`vehicleDetails` por `ariaLabel` ("Año", "Potencia"). CO₂ no está en el SRP.

### Cómo scrapearlo

- URL: `https://www.autoscout24.es/lst?atype=C&cy=E&page=N`
  (`cy=E` = España; `D` = Alemania; `.de` usa el mismo parser).
- `__NEXT_DATA__` se lee con un solo `httpx.get` con headers de navegador
  (verificado: 200, 20 anuncios). No hace falta Scrapfly.
- Paginación: `&page=N`. `numberOfPages` viene en el primer SRP.
- Mapper: traduce `fuel`/`transmission`/`seller.type` al vocabulario canónico
  y convierte `mileageInKm` español ("220.957 km" → 220957) y potencia a kW.

### Fixtures y tests

- Fixture real: `backend/tests/fixtures/autoscout24/srp.json` (2 anuncios).
- `backend/tests/scrapers/test_autoscout24.py`.

---

## 5. coches.net

### Cómo funciona la página

coches.net incrusta el estado SSR en:

```html
<script>window.__INITIAL_PROPS__ = JSON.parse("...")</script>
```

El payload es un **string JS escapado** (con `\"`), hay que decodificarlo en dos
pasos (el parser `_decode_payload` lo hace):

1. Extraer el literal de string JS (respetando escapes de barra).
2. `json.loads('"' + literal + '"')` → el JSON real.

Estructura (verificado en vivo 2026-08):

```
payload["initialResults"]["items"]          # ≈35 anuncios por página
payload["initialResults"]["totalResults"]
payload["initialResults"]["totalPages"]
payload["paginationPlaceholderUrl"]         # "/segunda-mano/?pg=%{pageNumber}"
```

Cada anuncio raw:

```json
{
  "id": "71090895",
  "url": "/ds-ds-7-crossback-...-71090895-covo.aspx",
  "make": "DS", "model": "DS 7 Crossback", "title": "DS DS 7 Crossback...",
  "price": 24995, "km": 61178, "year": 2021, "hp": 300,
  "fuelType": "Híbrido enchufable",
  "isProfessional": true,
  "location": {"mainProvince": "Barcelona", "cityLiteral": "Barcelona Capital"},
  "photos": ["https://a.ccdn.es/cnet/vehicles/..."]
}
```

Nota: el SRP **no expone transmisión** → `transmission=None` (unknown). `hp`
viene en CV; se convierte a kW (`hp * 0.7355`).

### Cómo scrapearlo

- URL: `https://www.coches.net/segunda-mano/` (página 1) y `?pg=N`.
  La URL antigua `/coches-ocasion.aspx` ya **no existe** (404).
- Coches.net intercala **páginas-challenge JS** sin `__INITIAL_PROPS__`
  (anti-bot intermitente). El scraper detecta la ausencia del marcador y eleva
  `RuntimeError` (no silencia); reintentar después de unos segundos suele pasar.
- Mapper: traduce `fuelType` y `isProfessional` → seller_type al vocabulario
  canónico; país fijo `ES`.

### Fixtures y tests

- Fixtures reales: `backend/tests/fixtures/coches_net/srp.json` (2 anuncios) y
  `blocked.html` (página-challenge).
- `backend/tests/scrapers/test_coches_net.py`.

---

## 6. Anti-bot y resiliencia

- **Headers realistas siempre** (User-Agent + Accept-Language del país).
- **403/429**: reintentos con backoff (`_fetch` de cada scraper); 403 de botas
  de seguridad se propaga como `RuntimeError` con diagnóstico.
- **Detección de bloqueo por contenido**: cuando el anti-bot devuelve 200 con
  una página-challenge, el parser no encuentra su marcador → el scraper eleva
  error (caso coches.net).
- **Proxy configurable**: `scraper_proxy` en `app/core/config.py` (lee `.env`).
- **Histórico sin red**: mobile.de tiene `wayback.py` como vía offline.
- **Respetar rate limits**: `scripts/scrape_mobile_de_once.ps1` y la frecuencia
  de beat (15 min) evitan ráfagas.

---

## 7. Cómo integrar una fuente nueva

1. Crear `backend/scrapers/<fuente>/` con `parser.py`, `mapper.py`, `scraper.py` 
   (`BaseScraper` requiere `source` y `run(max_pages, on_page)`).
2. Inspeccionar la fuente en vivo (JSON SSR: `__NEXT_DATA__`,
   `__INITIAL_STATE__`, etc.) y guardar un fixture real con 2+ anuncios.
3. Tests: `backend/tests/scrapers/test_<fuente>.py` (parser, mapper, scraper
   con `MockTransport`, casos de rechazo y 403).
4. Añadir la task Celery en `workers/tasks.py` (`scrape.<fuente>` usando
   `_run_scrape`) + beat en `workers/celery_app.py`.
5. Añadir el endpoint `POST /internal/scrapers/<fuente>` en
   `app/api/routes/internal.py` + tests.
6. Verificar end-to-end con `ingest_listings` sobre la DB de dev.

El pipeline compartido (ingesta, `condition_signals`, vehicle matching,
descarga de imágenes, CV) reutiliza el `NormalizedListing` sin cambios.