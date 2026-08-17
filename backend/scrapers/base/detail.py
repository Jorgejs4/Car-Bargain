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
_ERROR_TITLE_MARKERS = ("ups! parece que algo no va bien", "something went wrong", "erreur")


def is_error_page_title(value: str | None) -> bool:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    return any(marker in normalized for marker in _ERROR_TITLE_MARKERS)


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", html_lib.unescape(value)).strip()
    return value[:20000] if value else None


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
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in _DESCRIPTION_KEYS:
                candidate = _clean(child.get("text") if isinstance(child, dict) else child)
                if candidate and len(candidate) >= 20:
                    return candidate
            nested = _walk_description(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _walk_description(child)
            if nested:
                return nested
    return None


def extract_detail_text(raw_html: str) -> dict[str, str | None]:
    """Devuelve ``title`` y ``description`` desde HTML de detalle."""
    parser = _MetaParser()
    parser.feed(raw_html)

    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title
    description = parser.meta.get("og:description") or parser.meta.get("description")

    for script_id, script in parser.scripts:
        candidate: Any = None
        if script_id == "__NEXT_DATA__" or script.lstrip().startswith("{"):
            try:
                candidate = json.loads(script)
            except json.JSONDecodeError:
                candidate = None
        if candidate is not None:
            description = _walk_description(candidate) or description
            if not title:
                title = _walk_title(candidate)
        if description:
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
    match = re.search(
        r'"(?:sellerComment|sellerRemarks|dealerComment|dealerNotes|sellerText)"\s*:\s*"((?:\\.|[^"\\])*)"',
        raw_html,
        re.IGNORECASE,
    )
    if match:
        try:
            seller_comment = _clean(json.loads('"' + match.group(1) + '"'))
        except json.JSONDecodeError:
            seller_comment = _clean(match.group(1))
    clean_title = _clean(title)
    clean_description = _clean(description)
    if is_error_page_title(clean_title):
        clean_title = None
        clean_description = None
    return {
        "title": clean_title,
        "description": clean_description,
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
