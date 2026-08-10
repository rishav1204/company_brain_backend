"""Encrypt sensitive IAM secrets at rest (SEC-12)."""

from __future__ import annotations

import base64
import hashlib

from app.core.config import settings


class SecretEncryptionError(Exception):
    pass


def _encryption_key_material() -> bytes:
    key = (settings.integrations_credentials_key or "").strip()
    if not key:
        if settings.app_env.lower() == "prod":
            raise SecretEncryptionError("INTEGRATIONS_CREDENTIALS_KEY is required in production")
        key = (settings.jwt_secret or "").strip()
        if not key:
            raise SecretEncryptionError("No encryption key configured for IAM secrets")
    return key.encode()


def _fernet():
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(_encryption_key_material()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return "enc:v1:" + _fernet().encrypt(value.encode()).decode()
    except SecretEncryptionError:
        raise
    except Exception as exc:
        raise SecretEncryptionError(f"Failed to encrypt secret: {exc}") from exc


def decrypt_secret(value: str) -> str:
    if not value or not str(value).startswith("enc:v1:"):
        if settings.app_env.lower() == "prod" and value:
            raise SecretEncryptionError("Plaintext IAM secret found in production")
        return str(value or "")
    try:
        return _fernet().decrypt(str(value)[7:].encode()).decode()
    except SecretEncryptionError:
        raise
    except Exception as exc:
        raise SecretEncryptionError(f"Failed to decrypt secret: {exc}") from exc
