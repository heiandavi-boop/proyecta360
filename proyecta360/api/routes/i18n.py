from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from proyecta360.core.i18n import DEFAULT_LOCALE, FALLBACK_LOCALE, SUPPORTED_LANGUAGES, language_list, load_catalog, normalize_locale


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    static_dir = ctx.BASE_DIR / "static"

    @router.get("/api/i18n/languages")
    def languages() -> Dict[str, Any]:
        return {
            "default_locale": DEFAULT_LOCALE,
            "fallback_locale": FALLBACK_LOCALE,
            "languages": language_list(),
        }

    @router.get("/api/i18n/catalog/{locale}")
    def catalog(locale: str) -> Dict[str, Any]:
        code = normalize_locale(locale)
        return {
            "locale": code,
            "metadata": SUPPORTED_LANGUAGES[code],
            "messages": load_catalog(static_dir, code),
        }

    return router
