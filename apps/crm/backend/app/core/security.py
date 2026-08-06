from datetime import datetime, timedelta, timezone
from typing import Any
from argon2 import PasswordHasher
from jose import jwt

from app.core.config import get_settings

_hasher = PasswordHasher()
_ALGO = "HS256"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True iff `plain` matches the argon2 `hashed` string.

    Catches every conceivable failure. argon2-cffi 25 raises `InvalidHashError`
    (a `ValueError`) on corrupted hashes — it does NOT subclass `Argon2Error` —
    so a narrower except missed it and login returned 500. Semantically we want
    any verification failure to mean "credentials don't work" so the login path
    returns a clean 401.
    """
    try:
        return _hasher.verify(hashed, plain)
    except Exception:
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_expire_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.app_secret_key, algorithm=_ALGO)


def create_refresh_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=s.refresh_token_expire_days)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, s.app_secret_key, algorithm=_ALGO)


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(token, s.app_secret_key, algorithms=[_ALGO])
