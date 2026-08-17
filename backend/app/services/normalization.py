"""Normalización de texto para identidad de vehículo (Fase 5).

Estrategia:
- Marca/modelo/variante/generación se normalizan a minúsculas, sin acentos,
  con espacios colapsados y variantes comerciales estandarizadas
  (ej. `320 d` → `320d`, `xDrive` → `xdrive`, `M Sportpaket` → `m sportpaket`).
- La normalización es **reversible en dirección**: nunca pierde el valor raw
  (se conserva en `vehicle_matches.raw_value`).

Diccionarios y reglas acotados; si una regla no aplica, el texto queda igual
salvo el plegado de caja/acentos. No se inventan datos.
"""

import re
import unicodedata

_WS = re.compile(r"\s+")
# "320 d" → "320d"; "320d xDrive" se normaliza después. Solo une cifras y letras.
_DIGIT_LETTER_BOUNDARY = re.compile(r"(?<=\d)\s+(?=[A-Za-z])|(?<=[A-Za-z])\s+(?=\d)")

# Diccionario de variantes comerciales canónicas (minúsculas, sin acentos).
# Clave = variante tal cual (plegada), valor = canónica.
_VARIANT_CANONICAL = {
    "xdrive": "xdrive",
    "4matic": "4matic",
    "quattro": "quattro",
    "4x4": "4x4",
    "awd": "awd",
    "sdrive": "sdrive",
    "msport": "m sport",
    "m sport": "m sport",
    "m-sport": "m sport",
    "sport": "sport",
    "line": "line",
    "m line": "m line",
    "amg": "amg",
    "rline": "r line",
    "gt-line": "gt line",
    "gtline": "gt line",
    "d": "d",
    "i": "i",
    "e": "e",
    "cdi": "cdi",
    "tdi": "tdi",
    "dci": "dci",
    "gti": "gti",
    "gtd": "gtd",
    "st": "st",
    "st-line": "st line",
    "blue": "blue",
    "family": "family",
    "comfort": "comfort",
    "attraction": "attraction",
    "lounge": "lounge",
    "style": "style",
    "business": "business",
    "basic": "basic",
    "pure": "pure",
    "life": "life",
    "active": "active",
    "ambition": "ambition",
}

# Marcas frecuentes: normalizan su escritura (tildes, guiones, abreviatura).
_BRAND_CANONICAL = {
    "mercedes benz": "mercedes-benz",
    "mercedes-benz": "mercedes-benz",
    "mercedes": "mercedes-benz",
    "bmw": "bmw",
    "vw": "volkswagen",
    "volkswagen": "volkswagen",
    "audi": "audi",
    "opel": "opel",
    "ford": "ford",
    "renault": "renault",
    "peugeot": "peugeot",
    "citroen": "citroen",
    "citroën": "citroen",
    "skoda": "skoda",
    "Škoda": "skoda",
    "seat": "seat",
    "toyota": "toyota",
    "nissan": "nissan",
    "honda": "honda",
    "hyundai": "hyundai",
    "kia": "kia",
    "dacia": "dacia",
    "fiat": "fiat",
    "alfa romeo": "alfa romeo",
    "tesla": "tesla",
    "porsche": "porsche",
    "jaguar": "jaguar",
    "land rover": "land rover",
    "volvo": "volvo",
    "mini": "mini",
    "mazda": "mazda",
    "suzuki": "suzuki",
    "mitsubishi": "mitsubishi",
    "subaru": "subaru",
    "lexus": "lexus",
    "jeep": "jeep",
    "chevrolet": "chevrolet",
    "smart": "smart",
    "cupra": "cupra",
    "ds": "ds",
    "polestar": "polestar",
}


def fold(value: str) -> str:
    """Plegado de caja, acentos y espacios (no toca dígitos/puntuación)."""
    normalized = unicodedata.normalize("NFKD", value)
    folded = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    folded = folded.lower()
    return _WS.sub(" ", folded).strip()


def normalize_brand(value: str | None) -> str | None:
    """Normaliza una marca a su forma canónica, o `None` si es vacía."""
    if not value:
        return None
    folded = fold(value)
    return _BRAND_CANONICAL.get(folded, folded)


def _strip_variant_suffixes(folded: str) -> str:
    """`m sportpaket` → `m sport` (quita el sufijo `paket`)."""
    if folded.endswith("paket"):
        base = folded[: -len("paket")].strip()
        if base:
            return base
    return folded


def normalize_variant(value: str | None) -> str | None:
    """Normaliza la variante a una forma canónica, o `None` si es vacía."""
    if not value:
        return None
    folded = fold(value)
    folded = _strip_variant_suffixes(folded)
    # Variante compuesta: normaliza cada token y une con espacios.
    tokens = [token for token in folded.split() if token]
    normalized_tokens = [_VARIANT_CANONICAL.get(token, token) for token in tokens]
    return " ".join(normalized_tokens) or None


def normalize_model(value: str | None) -> str | None:
    """Normaliza el modelo: une cifras/letras contiguas (`320 d` → `320d`)."""
    if not value:
        return None
    folded = fold(value)
    joined = _DIGIT_LETTER_BOUNDARY.sub("", folded)
    return joined or None


def normalize_generation(value: str | None) -> str | None:
    if not value:
        return None
    folded = fold(value)
    return _WS.sub(" ", folded).strip() or None


def normalize_fuel(value: str | None) -> str | None:
    if not value:
        return None
    folded = fold(value)
    return {"petrol": "petrol", "gasolina": "petrol", "diesel": "diesel", "electric": "electric", "elektro": "electric"}.get(folded, folded)


def normalize_transmission(value: str | None) -> str | None:
    if not value:
        return None
    folded = fold(value)
    return {"manual": "manual", "automatic": "automatic", "automatik": "automatic"}.get(folded, folded)


def normalize_identity(**fields) -> dict[str, str | None]:
    """Devuelve el diccionario de identidad con cada campo normalizado."""
    return {
        "brand": normalize_brand(fields.get("brand")),
        "model": normalize_model(fields.get("model")),
        "generation": normalize_generation(fields.get("generation")),
        "variant": normalize_variant(fields.get("variant")),
        "fuel": normalize_fuel(fields.get("fuel")),
        "transmission": normalize_transmission(fields.get("transmission")),
    }
