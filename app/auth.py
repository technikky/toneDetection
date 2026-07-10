"""Stage 15: local teacher authentication -- deliberately no cloud
dependency (no Firebase/Auth0/Supabase), consistent with this app's
fully-offline design. Password hashing uses stdlib hashlib.scrypt, so no
extra dependency is needed either.

Sessions are an in-memory token -> {username, expires_at} map. They reset
on server restart -- an acceptable trade-off for a single-machine,
single-classroom tool; a teacher just logs in again.
"""
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request

SESSION_COOKIE = "sightsinging_session"
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

_sessions: dict[str, dict] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN)
    return hmac.compare_digest(actual, expected)


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"username": username, "expires_at": time.time() + SESSION_TTL_SECONDS}
    return token


def destroy_session(token: Optional[str]) -> None:
    if token:
        _sessions.pop(token, None)


def _session_for_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if session["expires_at"] < time.time():
        _sessions.pop(token, None)
        return None
    return session


def current_username(request: Request) -> Optional[str]:
    return_session = _session_for_token(request.cookies.get(SESSION_COOKIE))
    return return_session["username"] if return_session else None


def current_username_ws(cookies: dict) -> Optional[str]:
    session = _session_for_token(cookies.get(SESSION_COOKIE))
    return session["username"] if session else None


def require_teacher_api(request: Request) -> str:
    """FastAPI dependency for JSON API routes: 401s cleanly if not logged in."""
    username = current_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="Teacher login required.")
    return username
