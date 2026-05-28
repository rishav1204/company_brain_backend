from __future__ import annotations

import hashlib
import hmac


def verify_hmac_sha256(*, secret: str, payload: bytes, signature_hex: str) -> bool:
    if not secret or not signature_hex:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex.strip())

