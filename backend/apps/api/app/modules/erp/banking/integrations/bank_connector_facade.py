from __future__ import annotations

from app.modules.platform.integrations.services.connector_registry import connector_registry


def resolve_bank_connector(provider: str = "stub_bank"):
    return connector_registry.resolve(connector_type="bank", provider_name=provider)
