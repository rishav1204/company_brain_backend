from __future__ import annotations

from app.modules.platform.integrations.security.signature_validator import verify_hmac_sha256


def test_verify_hmac_sha256_ok() -> None:
    secret = "s3cr3t"
    payload = b'{"a":1}'
    import hashlib, hmac

    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_hmac_sha256(secret=secret, payload=payload, signature_hex=sig) is True


def test_verify_hmac_sha256_bad() -> None:
    assert verify_hmac_sha256(secret="a", payload=b"x", signature_hex="deadbeef") is False

