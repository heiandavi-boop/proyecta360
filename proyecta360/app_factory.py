from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from proyecta360.api.routers import build_api_router
from proyecta360.core.http import add_security_headers, audited_api_mutation, cors_origins, protected_api_request, role_allowed


def create_app(
    *,
    base_dir: Path,
    lifespan,
    ctx: Any,
    db: Callable[[], sqlite3.Connection],
    user_from_authorization: Callable[[sqlite3.Connection, Optional[str]], Optional[dict]],
) -> FastAPI:
    docs_enabled = os.getenv("PROYECTA360_ENABLE_DOCS", "").lower() in {"1", "true", "yes"}
    app = FastAPI(
        title="PRUNIN API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def enforce_api_authorization(request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        user = None
        if protected_api_request(path, method):
            authorization = request.headers.get("Authorization")
            with db() as conn:
                user = user_from_authorization(conn, authorization)
            if not user:
                return add_security_headers(JSONResponse(status_code=401, content={"detail": "Sesion requerida"}), True)
            if not role_allowed(path, method, user["role"]):
                return add_security_headers(JSONResponse(status_code=403, content={"detail": "Permisos insuficientes"}), True)
            request.state.current_user = user
        response = await call_next(request)
        if user and audited_api_mutation(path, method):
            try:
                with db() as conn:
                    conn.execute(
                        """INSERT INTO audit_events (user_id, actor_email, actor_role, method, path, status_code, client_host)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            user.get("id"),
                            user.get("email", ""),
                            user.get("role", ""),
                            method,
                            path,
                            response.status_code,
                            request.client.host if request.client else "",
                        ),
                    )
                    conn.commit()
            except Exception:
                pass
        return add_security_headers(response, path.startswith("/api/"))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Convert pydantic validation errors into user-friendly messages
        errors = exc.errors()
        messages = []
        for err in errors:
            loc = err.get("loc") or []
            # field name is last location element when available
            field = str(loc[-1]) if loc else "campo"
            msg_type = err.get("type", "")
            if msg_type.endswith("value_error.missing") or msg_type.endswith("required"):
                messages.append(f"El campo '{field}' es obligatorio.")
            else:
                # Use the provided message but keep it user-friendly
                msg = err.get("msg", "Entrada inválida")
                messages.append(str(msg))
        if not messages:
            messages = ["Entrada inválida. Revisa los campos obligatorios y su formato."]
        # Return combined message without exposing internal trace
        return add_security_headers(JSONResponse(status_code=422, content={"detail": " ".join(messages)}), True)

    frontend_dist = base_dir / "frontend" / "dist"
    frontend_assets = frontend_dist / "assets"
    app.include_router(build_api_router(ctx))
    if frontend_assets.exists():
        app.mount("/assets", StaticFiles(directory=frontend_assets), name="react-assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(base_dir / "static" / "favicon.svg", media_type="image/svg+xml")

    return app
