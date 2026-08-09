from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import sqlite3


def hash_password(password: str) -> str:
    iterations = int(os.getenv("PROYECTA360_PASSWORD_ITERATIONS", "260000"))
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def legacy_hash_password(password: str) -> str:
    return hashlib.sha256((password + "::proyecta360-demo").encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    parts = (stored_hash or "").split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
            return hmac.compare_digest(digest, parts[3])
        except Exception:
            return False
    return hmac.compare_digest(stored_hash or "", legacy_hash_password(password))


def password_needs_rehash(stored_hash: str) -> bool:
    parts = (stored_hash or "").split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return True
    try:
        return int(parts[1]) < int(os.getenv("PROYECTA360_PASSWORD_ITERATIONS", "260000"))
    except ValueError:
        return True


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "organization_id": user.get("organization_id", 1),
    }


def user_from_authorization(
    conn: sqlite3.Connection,
    authorization: Optional[str],
    find_one: Callable[[sqlite3.Connection, str, tuple], Dict[str, Any] | None],
) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = raw_token.strip()
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return find_one(conn, "SELECT * FROM users WHERE access_token_hash = ?", (token_hash,))


def safe_filename(filename: str) -> str:
    name = Path(filename or "evidencia.bin").name
    cleaned = "".join(ch if ch.isalnum() or ch in ".-_ " else "_" for ch in name).strip()
    return cleaned or "evidencia.bin"
