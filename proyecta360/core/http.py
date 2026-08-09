from __future__ import annotations

import os
from typing import List


MUTATION_ROLES = {"Administrador", "Project Manager"}
READ_ROLES = {"Administrador", "Project Manager", "Consulta"}
ADMIN_ONLY_PREFIXES = ("/api/ops/",)
ADMIN_ONLY_EXACT = {"/api/seed", "/api/ai/settings"}


def cors_origins() -> List[str]:
    raw = os.getenv("PROYECTA360_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
    return [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


def protected_api_request(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return False
    if not path.startswith("/api/"):
        return False
    if path in {"/api/auth/login", "/api/health", "/api/health/ready"} or path.startswith("/api/i18n/"):
        return False
    return True


def role_allowed(path: str, method: str, role: str) -> bool:
    if path in ADMIN_ONLY_EXACT or any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
        return role == "Administrador"
    if method == "GET":
        return role in READ_ROLES
    return role in MUTATION_ROLES


def audited_api_mutation(path: str, method: str) -> bool:
    return path.startswith("/api/") and method not in {"GET", "HEAD", "OPTIONS"} and not path.startswith("/api/auth/")


def add_security_headers(response, api_response: bool = False):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cache-Control", "no-store" if api_response else "no-cache")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response
