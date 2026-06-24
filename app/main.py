"""Application factory and entrypoint.

``create_app()`` builds the FastAPI instance; the module-level ``app`` is what
uvicorn serves (``uvicorn app:app`` resolves via app/__init__.py). Schema
migrations and demo seeding run in the lifespan handler at startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import connect, run_migrations
from app.routers import all_routers
from app.seed import seed_database
from core.config import BASE_DIR, settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    if settings.seed_on_startup:
        conn = connect()
        try:
            seed_database(conn)
        finally:
            conn.close()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="Proyecta360 API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in all_routers:
        application.include_router(router)

    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @application.get("/")
    def index() -> FileResponse:
        return FileResponse(BASE_DIR / "static" / "index.html")

    @application.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")

    return application


app = create_app()
