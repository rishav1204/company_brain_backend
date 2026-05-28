from __future__ import annotations

import base64
import json
from hashlib import sha256

from app.core.config import settings


class CredentialManager:
    """
    Encrypt/decrypt connector credentials for at-rest storage.

    This is a minimal envelope suitable for dev/staging. In production, replace with KMS/Vault.
    """

    def _fernet(self):
        from cryptography.fernet import Fernet

        key = (settings.integrations_credentials_key or "").strip()
        if not key:
            raise RuntimeError("INTEGRATIONS_CREDENTIALS_KEY is required to store connector credentials")
        # Allow passing raw bytes-like secret; normalize to Fernet key (urlsafe_b64 32 bytes).
        if len(key) < 40:
            digest = sha256(key.encode()).digest()
            key = base64.urlsafe_b64encode(digest).decode()
        return Fernet(key.encode())

    def encrypt_json(self, value: dict) -> str:
        raw = json.dumps(value or {}, separators=(",", ":"), sort_keys=True).encode()
        return self._fernet().encrypt(raw).decode()

    def decrypt_json(self, token: str) -> dict:
        raw = self._fernet().decrypt((token or "").encode())
        return json.loads(raw.decode())


credential_manager = CredentialManager()

