"""Utilidades comunes para extraer texto de páginas de detalle.

Las páginas de listado suelen traer precio y fotos, pero no la descripción del
vendedor. Esta utilidad soporta metadatos HTML, JSON-LD y estados SSR comunes
sin depender de un proveedor de IA ni de una API de pago.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from html.parser import HTMLParser
from typing import Any

_DESCRIPTION_KEYS = {
    "description",
    "descriptiontext",
    "sellerdescription",
    "addescription",
    "vehicledescription",
    "longdescription",
    "remarks",
    "comment",
    "commentaire",
    "omschrijving",
}
_TITLE_KEYS = {"title", "adtitle", "vehicletitle", "headline", "name"}
_SELLER_COMMENT_RE = re.compile(
    r'"(?:sellerComment|sellerRemarks|dealerComment|dealerNotes|sellerText)"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.IGNORECASE,
)


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", html_lib.unescape(value)).strip()
    return value[:20000] if value else None


def extract_variant_from_title(title: str | None, brand: str | None, model: str | None) -> str | None:
    """Extrae la parte posterior a marca/modelo de títulos de portales."""
    if not title or not brand or not model:
        return None
    value = re.sub(r"\s+", " ", title).strip()
    prefix = re.compile(
        rf"^\s*{re.escape(brand)}\s+{re.escape(model)}(?:\s+{re.escape(model)})?\s*",
        re.IGNORECASE,
    )
    variant = prefix.sub("", value, count=1).strip(" -|/")
    return variant or None


def extract_record_description(record: dict) -> str | None:
    """Busca una descripción en un registro SSR sin asumir un único nombre."""
    found: list[str] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                normalized = re.sub(r"[^a-z]", "", str(child_key).lower())
                if normalized in _DESCRIPTION_KEYS:
                    candidate = _clean(child.get("text") if isinstance(child, dict) else child)
                    if candidate and len(candidate) >= 20:
                        found.append(candidate)
                elif isinstance(child, (dict, list)):
                    walk(child, normalized)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)

    walk(record)
    return max(found, key=len, default=None)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.scripts: list[tuple[str, str]] = []
        self._script_type = ""
        self._script_id = ""
        self._script_data: list[str] = []
        self._title_data: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name] = content
        elif tag.lower() == "script":
            self._script_type = attrs_dict.get("type", "")
            self._script_id = attrs_dict.get("id", "")
            self._script_data = []
        elif tag.lower() == "title":
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._script_type or self._script_id:
            self._script_data.append(data)
        if self._in_title:
            self._title_data.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script":
            if self._script_data:
                self.scripts.append((self._script_id, "".join(self._script_data)))
            self._script_type = ""
            self._script_id = ""
            self._script_data = []
        elif tag.lower() == "title":
            self._in_title = False

    @property
    def title(self) -> str | None:
        return _clean(" ".join(self._title_data))


def _walk_description(value: Any) -> str | None:
    candidates: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                if normalized in _DESCRIPTION_KEYS:
                    candidate = _clean(child.get("text") if isinstance(child, dict) else child)
                    if candidate and len(candidate) >= 20:
                        candidates.append(candidate)
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return max(candidates, key=len, default=None)


def extract_detail_text(raw_html: str) -> dict[str, str | None]:
    """Devuelve ``title`` y ``description`` desde HTML de detalle."""
    parser = _MetaParser()
    parser.feed(raw_html)

    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title
    description = parser.meta.get("og:description") or parser.meta.get("description")

    for script_id, script in parser.scripts:
        candidate: Any = None
        candidate_description: str | None = None
        if script_id == "__NEXT_DATA__" or script.lstrip().startswith("{"):
            try:
                candidate = json.loads(script)
            except json.JSONDecodeError:
                candidate = None
        if candidate is not None:
            candidate_description = _walk_description(candidate)
            description = candidate_description or description
            if not title:
                title = _walk_title(candidate)
        if candidate_description:
            break

    # Último fallback para estados JS que no son JSON puro.
    if not description:
        match = re.search(
            r'"(?:description|descriptionText|sellerDescription|longDescription)"\s*:\s*"((?:\\.|[^"\\])*)"',
            raw_html,
            re.IGNORECASE,
        )
        if match:
            try:
                description = _clean(json.loads('"' + match.group(1) + '"'))
            except json.JSONDecodeError:
                description = _clean(match.group(1))

    seller_comment = None
    match = _SELLER_COMMENT_RE.search(raw_html)
    if match:
        try:
            seller_comment = _clean(json.loads('"' + match.group(1) + '"'))
        except json.JSONDecodeError:
            seller_comment = _clean(match.group(1))
    return {
        "title": _clean(title),
        "description": _clean(description),
        "seller_comment": seller_comment,
    }


def _walk_title(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in _TITLE_KEYS:
                candidate = _clean(child)
                if candidate and len(candidate) >= 4:
                    return candidate
            nested = _walk_title(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _walk_title(child)
            if nested:
                return nested
    return None
