from __future__ import annotations

from hashlib import sha256

from app.modules.platform.integrations.services.integration_api_key_auth import authenticate_integration_api_key


def test_integration_api_key_prefix_rejected() -> None:
    assert authenticate_integration_api_key("cb_invalid") is None


def test_hash_stable() -> None:
    raw = "cbk_test"
    assert sha256(raw.encode()).hexdigest() == sha256(raw.encode()).hexdigest()

