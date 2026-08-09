from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request

from proyecta360.schemas.api import AuthLoginIn

LOGIN_ATTEMPTS: Dict[str, list[datetime]] = {}
MAX_LOGIN_ATTEMPTS = 8
LOGIN_WINDOW_MINUTES = 10


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    db = ctx.db
    hash_password = ctx.hash_password
    hash_token = ctx.hash_token
    init_db = ctx.init_db
    one = ctx.one
    public_user = ctx.public_user
    user_from_authorization = ctx.user_from_authorization
    verify_password = ctx.verify_password
    password_needs_rehash = ctx.password_needs_rehash
    TOKEN_TTL_MINUTES = ctx.TOKEN_TTL_MINUTES

    def rate_limit_key(request: Request, email: str) -> str:
        client = request.client.host if request.client else "unknown"
        return f"{client}:{email.lower().strip()}"

    def assert_login_not_limited(request: Request, email: str) -> None:
        key = rate_limit_key(request, email)
        cutoff = datetime.utcnow() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(key, []) if ts > cutoff]
        LOGIN_ATTEMPTS[key] = attempts
        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta de nuevo más tarde.")

    def register_failed_login(request: Request, email: str) -> None:
        key = rate_limit_key(request, email)
        LOGIN_ATTEMPTS.setdefault(key, []).append(datetime.utcnow())

    def clear_failed_logins(request: Request, email: str) -> None:
        LOGIN_ATTEMPTS.pop(rate_limit_key(request, email), None)

    async def read_login_payload(request: Request) -> AuthLoginIn:
        content_type = request.headers.get("content-type", "")
        try:
            if "application/json" in content_type:
                raw = await request.json()
            else:
                body = (await request.body()).decode("utf-8")
                raw = {key: values[-1] for key, values in parse_qs(body).items()}
            return AuthLoginIn(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Credenciales inválidas o incompletas") from exc

    @router.post("/api/auth/login")
    async def login(request: Request) -> Dict[str, Any]:
        payload = await read_login_payload(request)
        assert_login_not_limited(request, payload.email)
        init_db()
        with db() as conn:
            user = one(conn, "SELECT * FROM users WHERE lower(email) = lower(?)", (payload.email,))
            if not user or not verify_password(payload.password, user["password_hash"]):
                register_failed_login(request, payload.email)
                raise HTTPException(status_code=401, detail="Correo o contraseña inválidos")
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat()
            new_password_hash = hash_password(payload.password) if password_needs_rehash(user["password_hash"]) else user["password_hash"]
            conn.execute(
                "UPDATE users SET password_hash = ?, access_token = '', access_token_hash = ?, token_expires_at = ? WHERE id = ?",
                (new_password_hash, hash_token(token), expires_at, user["id"]),
            )
            conn.commit()
            clear_failed_logins(request, payload.email)
            user = one(conn, "SELECT * FROM users WHERE id = ?", (user["id"],))
            return {"token": token, "user": public_user(user)}
    
    
    @router.post("/api/auth/logout")
    def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
        init_db()
        with db() as conn:
            user = user_from_authorization(conn, authorization)
            if user:
                conn.execute("UPDATE users SET access_token = '', access_token_hash = '', token_expires_at = '' WHERE id = ?", (user["id"],))
                conn.commit()
        return {"message": "Sesión cerrada"}
    
    
    @router.get("/api/auth/me")
    def me(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            user = user_from_authorization(conn, authorization)
            if not user:
                raise HTTPException(status_code=401, detail="Sesión no iniciada")
            return {"user": public_user(user)}
    

    return router


