"""Password/session helpers. Secrets are never stored in source control."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ROUNDS = 310_000
SESSION_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def new_session() -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(36)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    expiry = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    return raw, digest, expiry


def session_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def secret_key() -> bytes:
    value = os.getenv("APP_SECRET", "local-development-only-change-me")
    return value.encode()


def new_csrf() -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(secret_key(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def csrf_matches(cookie: str | None, header: str | None) -> bool:
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        return False
    try:
        nonce, signature = cookie.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(secret_key(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
