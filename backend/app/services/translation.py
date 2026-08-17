"""Traducción gratuita y tolerante a fallos para la interfaz."""

from functools import lru_cache

import httpx

_LANG_BY_COUNTRY = {"DE": "de", "AT": "de", "FR": "fr", "IT": "it", "NL": "nl", "BE": "nl", "ES": "es"}

@lru_cache(maxsize=512)
def translate_to_spanish(text: str, source_language: str) -> str | None:
    if not text or source_language == "es":
        return text or None
    try:
        response = httpx.get("https://api.mymemory.translated.net/get", params={"q": text[:5000], "langpair": f"{source_language}|es"}, timeout=15)
        response.raise_for_status()
        translated = response.json().get("responseData", {}).get("translatedText")
        return translated.strip() if isinstance(translated, str) and translated.strip() else None
    except (httpx.HTTPError, ValueError, KeyError):
        return None

def language_for_country(country: str | None) -> str:
    return _LANG_BY_COUNTRY.get((country or "").upper(), "en")
