"""Symmetric field encryption for sensitive strings (OAuth tokens, secrets).

Uses cryptography.fernet with a base64-urlsafe key read from settings. If the
key is missing, callers get a clear error at write time — we never silently
store plaintext.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger("jarvis.crypto")


def _fernet() -> Fernet:
    raw = get_settings().field_encryption_key.strip()
    if not raw:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    # Accept either a proper Fernet key (44-char base64) or an arbitrary secret
    # (which we hash + base64-encode to 32 bytes for convenience).
    key: bytes
    try:
        key = raw.encode() if len(raw) == 44 else base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        return Fernet(key)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"invalid FIELD_ENCRYPTION_KEY: {e}") from None


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string.

    Returns "" for empty input or on invalid/corrupt ciphertext. Invalid tokens
    are logged at WARNING so operators notice silent decryption failures (for
    example after a key rotation). A missing/unconfigured key still raises
    RuntimeError — that's a config error, not a per-value failure.
    """
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("fernet_decrypt_failed len=%d prefix=%s", len(ciphertext), ciphertext[:8])
        return ""
