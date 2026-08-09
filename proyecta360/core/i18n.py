from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_LOCALE = "es"
FALLBACK_LOCALE = "es"

SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"code": "en", "label": "English", "native": "English", "flag": "us", "dir": "ltr", "locale": "en-US"},
    "zh": {"code": "zh", "label": "Mandarin Chinese", "native": "Chinese", "flag": "cn", "dir": "ltr", "locale": "zh-CN"},
    "hi": {"code": "hi", "label": "Hindi", "native": "Hindi", "flag": "in", "dir": "ltr", "locale": "hi-IN"},
    "es": {"code": "es", "label": "Spanish", "native": "Espanol", "flag": "co", "dir": "ltr", "locale": "es-CO"},
    "ar": {"code": "ar", "label": "Arabic", "native": "Arabic", "flag": "sa", "dir": "rtl", "locale": "ar-SA"},
}


def language_list() -> List[Dict[str, str]]:
    return list(SUPPORTED_LANGUAGES.values())


def normalize_locale(locale: str | None) -> str:
    code = (locale or DEFAULT_LOCALE).split("-")[0].lower()
    return code if code in SUPPORTED_LANGUAGES else FALLBACK_LOCALE


def catalog_path(static_dir: Path, locale: str | None) -> Path:
    return static_dir / "i18n" / f"{normalize_locale(locale)}.json"


def load_catalog(static_dir: Path, locale: str | None) -> Dict[str, Any]:
    path = catalog_path(static_dir, locale)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
