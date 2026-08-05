from __future__ import annotations

import hashlib
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


SECRET_PREFIX = "fernet:v1:"


def encrypt_secret(value: str | None, *, settings: Settings | None = None) -> str | None:
    normalized = value.strip() if value is not None else ""
    if not normalized:
        return None
    token = _fernet(settings or get_settings()).encrypt(normalized.encode("utf-8"))
    return SECRET_PREFIX + token.decode("ascii")


def decrypt_secret(value: str | None, *, settings: Settings | None = None) -> str | None:
    if not value:
        return None
    if not value.startswith(SECRET_PREFIX):
        raise ValueError("Stored secret is not encrypted with a supported format.")
    try:
        return _fernet(settings or get_settings()).decrypt(
            value.removeprefix(SECRET_PREFIX).encode("ascii")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Stored secret could not be decrypted with the configured encryption key."
        ) from exc


def _fernet(settings: Settings) -> Fernet:
    secret = (settings.secret_encryption_key or settings.ai_key_encryption_key or "").strip()
    if not secret:
        raise ValueError(
            "VULNFLANKER_SECRET_ENCRYPTION_KEY is required to save or decrypt SMTP credentials."
        )
    key = urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)
