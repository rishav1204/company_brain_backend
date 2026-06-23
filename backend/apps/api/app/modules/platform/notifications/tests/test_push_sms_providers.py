"""Tests for notification provider configuration behavior."""
from __future__ import annotations

from app.modules.platform.notifications.providers.push_provider import push_provider
from app.modules.platform.notifications.providers.sms_provider import sms_provider


def test_push_skipped_when_api_not_configured(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "push_api_url", "")
    result = push_provider.send(user_id="u1", title="t", body="b")
    assert result.status == "skipped"


def test_sms_skipped_when_api_not_configured(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "sms_api_url", "")
    result = sms_provider.send(to="+10000000000", body="hello")
    assert result.status == "skipped"
