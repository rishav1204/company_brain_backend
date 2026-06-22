from __future__ import annotations

import hashlib
import hmac


def sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature or "")
