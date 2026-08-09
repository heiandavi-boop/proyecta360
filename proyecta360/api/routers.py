from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from proyecta360.api.routes import ai, auth, core, evidences, i18n, management, projects, scrum, tasks


def build_api_router(ctx: Any) -> APIRouter:
    router = APIRouter()
    for module in (core, i18n, projects, tasks, scrum, management, ai, auth, evidences):
        router.include_router(module.build_router(ctx))
    return router
