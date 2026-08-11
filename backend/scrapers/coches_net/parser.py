"""Parser de coches.net (SRP) desde el JSON embebido en `window.__INITIAL_PROPS__`.

coches.net es una SPA que incrusta el estado SSR en:

    window.__INITIAL_PROPS__ = JSON.parse("...")

El payload es un string JS escapado (con `\"`), así que se decodifica en dos
pasos: primero el literal de string JS y luego el JSON resultante.

Estructura real verificada en vivo (2026-08, fixture `srp.json`):
- `initialResults["items"]`: lista de anuncios (≈35 por página).
- `initialResults["totalResults"]` / `totalPages`: contadores.
- Paginación con `?pg=N` (`paginationPlaceholderUrl`).

Nota anti-bot: coches.net intercala páginas de bloqueo JS ("Ups! Parece que
algo no va bien...") sin `__INITIAL_PROPS__`. En ese caso el parser devuelve
una lista vacía, y el scraper debe detectar la page vacía como bloqueo.
"""

import json


class ParseError(ValueError):
    """La respuesta no contiene datos de anuncios reconocibles."""


_BLOCKED_MARKER = "window.__INITIAL_PROPS__"


def _extract_js_string_literal(html: str) -> str:
    """Extrae el interior de `JSON.parse("...")` respetando escapes de barra."""
    index = html.find(_BLOCKED_MARKER)
    if index < 0:
        raise ParseError("No se encontró window.__INITIAL_PROPS__ (posible bloqueo anti-bot)")
    start_parse = html.find('= JSON.parse("', index)
    if start_parse < 0:
        raise ParseError("window.__INITIAL_PROPS__ no usa JSON.parse")
    out: list[str] = []
    escaped = False
    j = start_parse + len('= JSON.parse("')
    while j < len(html):
        char = html[j]
        if escaped:
            out.append(char)
            escaped = False
        elif char == "\\":
            # se conserva la barra para poder decodificar el literal con json.loads
            out.append(char)
            escaped = True
        elif char == '"':
            return "".join(out)
        else:
            out.append(char)
        j += 1
    raise ParseError("Literal de string JS sin cerrar")


def _decode_payload(html: str) -> dict:
    literal = _extract_js_string_literal(html)
    # El literal es un string JSON escapado; decodificarlo una vez da el JSON real.
    decoded = json.loads('"' + literal + '"')
    if isinstance(decoded, str):
        decoded = json.loads(decoded)
    if not isinstance(decoded, dict):
        raise ParseError("El payload de __INITIAL_PROPS__ no es un objeto")
    return decoded


class CochesNetParser:
    """Extrae registros raw de un HTML de SRP o de un estado JSON ya parseado."""

    def parse(self, raw: str | dict) -> list[dict]:
        if isinstance(raw, dict):
            state: dict = raw
        else:
            state = _decode_payload(raw)
        results = state.get("initialResults") or state
        items = results.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]