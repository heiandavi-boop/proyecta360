from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    bootstrap_payload = ctx.bootstrap_payload
    all_rows = ctx.all_rows
    APP_ENV = ctx.APP_ENV
    DATABASE_BACKEND = ctx.DATABASE_BACKEND
    db = ctx.db
    init_db = ctx.init_db
    portfolio_summary = ctx.portfolio_summary
    public_user = ctx.public_user
    seed_database = ctx.seed_database
    user_from_authorization = ctx.user_from_authorization

    @router.get("/api/portfolio")
    def get_portfolio() -> Dict[str, Any]:
        init_db()
        with db() as conn:
            return {"projects": portfolio_summary(conn)}

    @router.get("/api/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "app": "Proyecta360", "time": datetime.utcnow().isoformat()}

    @router.get("/api/health/ready")
    def ready() -> Dict[str, Any]:
        checks: Dict[str, Any] = {"database": "unknown"}
        status = "ok"
        try:
            with db() as conn:
                conn.execute("SELECT 1").fetchone()
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = str(exc)
            status = "error"
        return {
            "status": status,
            "app": "Proyecta360",
            "environment": APP_ENV,
            "database_backend": DATABASE_BACKEND,
            "checks": checks,
            "time": datetime.utcnow().isoformat(),
        }

    @router.get("/api/bootstrap")
    def bootstrap(project_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            payload = bootstrap_payload(conn, project_id)
            payload["current_user"] = public_user(user_from_authorization(conn, authorization))
            return payload

    @router.post("/api/seed")
    def seed() -> Dict[str, str]:
        init_db()
        with db() as conn:
            seed_database(conn)
        return {"message": "Datos base cargados"}

    @router.get("/api/ops/metrics")
    def operational_metrics() -> Dict[str, Any]:
        init_db()
        with db() as conn:
            counts = {
                "projects": all_rows(conn, "SELECT COUNT(*) AS total FROM projects")[0]["total"],
                "users": all_rows(conn, "SELECT COUNT(*) AS total FROM users")[0]["total"],
                "audit_events": all_rows(conn, "SELECT COUNT(*) AS total FROM audit_events")[0]["total"],
                "ai_runs": all_rows(conn, "SELECT COUNT(*) AS total FROM ai_analysis_runs")[0]["total"],
            }
            recent_audit = all_rows(conn, "SELECT actor_email, actor_role, method, path, status_code, created_at FROM audit_events ORDER BY created_at DESC, id DESC LIMIT 20")
        return {
            "status": "ok",
            "environment": APP_ENV,
            "database_backend": DATABASE_BACKEND,
            "counts": counts,
            "recent_audit": recent_audit,
            "time": datetime.utcnow().isoformat(),
        }

    return router
