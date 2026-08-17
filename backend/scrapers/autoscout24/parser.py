"""Parser de AutoScout24 (SRP) desde el JSON embebido en `__NEXT_DATA__`.

AutoScout24 es una SPA Next.js: cada página incrusta
`<script id="__NEXT_DATA__" type="application/json">...</script>` con todo el
estado SSR. Este parser extrae ese JSON y devuelve los anuncios como registros
raw (dicts).

Estructura real verificada en vivo contra `https://www.autoscout24.es/lst`
(agosto 2026, fixture `srp.json`):
- `props["pageProps"]["listings"]`: lista de anuncios (20 por página).
- `props["pageProps"]["numberOfResults"]` / `numberOfPages`: contadores.
- Paginación con `?page=N` (todas las páginas usan el mismo `__NEXT_DATA__`).
- Si el script no está o no hay `listings`, se devuelve una lista vacía.
"""

import json
import re

_NEXT_DATA_MARKER = "__NEXT_DATA__"
_SCRIPT_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class ParseError(ValueError):
    """La respuesta no contiene datos de anuncios reconocibles."""


def _extract_next_data(html: str) -> str:
    match = _SCRIPT_RE.search(html)
    if match:
        return match.group(1)
    index = html.find(_NEXT_DATA_MARKER)
    if index < 0:
        raise ParseError("No se encontró __NEXT_DATA__ en la página")
    start = html.find(">", index) + 1
    end = html.find("</script>", start)
    if start < 0 or end < 0 or end <= start:
        raise ParseError("__NEXT_DATA__ no contiene un script válido")
    return html[start:end]


class AutoScout24Parser:
    """Extrae registros raw de un HTML de SRP o de un estado JSON ya parseado."""

    def parse(self, raw: str | dict) -> list[dict]:
        if isinstance(raw, dict):
            state: dict = raw
        else:
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                state = json.loads(_extract_next_data(raw))
        page_props = state.get("props", {}).get("pageProps", {})
        items = page_props.get("listings")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]