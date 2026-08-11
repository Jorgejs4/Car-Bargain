"""Parser de la página de búsqueda (SRP) de mobile.de.

La SPA de mobile.de incrusta el estado SSR en `window.__INITIAL_STATE__`.
Este parser extrae ese JSON y devuelve los anuncios como registros raw (dicts).

Estructura real verificada contra un snapshot del Wayback Machine de
`suchen.mobile.de/fahrzeuge/search.html` (2025-12-05, fixture `search_page.html`):
- `state["search"]["srp"]["data"]["searchResults"]["items"]`: lista de anuncios.
- Paginación en `searchResults`: `page`, `numPages`, `hasNextPage`.
- Si `srp.data` es `None` (página de consent, shell sin SSR o sin resultados),
  se devuelve una lista vacía en lugar de fallar.

Se conserva un fallback a la estructura antigua `searchResult.ads` (dict o lista).
"""

import json

_INITIAL_STATE_MARKER = "window.__INITIAL_STATE__"


class ParseError(ValueError):
    """La respuesta no contiene datos de anuncios reconocibles."""


def _extract_state_from_html(html: str) -> dict:
    index = html.find(_INITIAL_STATE_MARKER)
    if index < 0:
        raise ParseError("No se encontró window.__INITIAL_STATE__ en la página")
    start = html.find("{", index)
    if start < 0:
        raise ParseError("window.__INITIAL_STATE__ no contiene un objeto JSON")
    try:
        state, _ = json.JSONDecoder().raw_decode(html[start:])
    except json.JSONDecodeError as exc:
        raise ParseError(f"window.__INITIAL_STATE__ no es JSON válido: {exc}") from exc
    return state


def _flatten_ad_items(items: list) -> list[dict]:
    """Descarta banners (`inlineAdvertising`) y aplana contenedores `page1Ads`."""
    flattened: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("id") is not None:
            flattened.append(item)
        elif item.get("type") == "page1Ads":
            nested = item.get("items")
            if isinstance(nested, list):
                flattened.extend(_flatten_ad_items(nested))
    return flattened


def _extract_items(data: dict) -> list[dict]:
    """Devuelve la lista de anuncios desde `srp.data`, tolerando las dos estructuras."""
    results = data.get("searchResults")
    if isinstance(results, dict):
        items = results.get("items")
        if isinstance(items, list):
            return _flatten_ad_items(items)
    result = data.get("searchResult") or {}
    ads = result.get("ads") or []
    if isinstance(ads, dict):
        ads = list(ads.values())
    return _flatten_ad_items(ads)


class MobileDeParser:
    """Extrae registros raw de un HTML de SRP o de un estado JSON ya parseado."""

    def parse(self, raw: str | dict) -> list[dict]:
        if isinstance(raw, dict):
            state: dict = raw
        else:
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                state = _extract_state_from_html(raw)
        srp = state.get("search", {}).get("srp", {})
        data = srp.get("data")
        if not isinstance(data, dict):
            return []
        return _extract_items(data)
