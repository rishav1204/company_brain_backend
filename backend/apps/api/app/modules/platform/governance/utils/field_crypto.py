from __future__ import annotations

import base64
import hashlib
import os


def encrypt_field(value: str, *, key_env: str = "GOVERNANCE_FIELD_ENCRYPTION_KEY") -> str:
    """Optional Fernet encryption when key is configured; otherwise deterministic hash prefix."""
    raw_key = os.getenv(key_env, "").strip()
    if not raw_key:
        digest = hashlib.sha256(value.encode()).hexdigest()[:16]
        return f"enc:hash:{digest}"
    try:
        from cryptography.fernet import Fernet

        key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
        return f"enc:fernet:{Fernet(key).encrypt(value.encode()).decode()}"
    except Exception:
        digest = hashlib.sha256(value.encode()).hexdigest()[:16]
        return f"enc:hash:{digest}"
