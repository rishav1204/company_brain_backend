from app.modules.platform.events.services.webhook_service import sign_payload


def test_hmac_signature_deterministic() -> None:
    body = b'{"event":"test"}'
    a = sign_payload("secret-key", body)
    b = sign_payload("secret-key", body)
    assert a == b
    assert len(a) == 64
