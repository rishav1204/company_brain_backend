from __future__ import annotations

from app.modules.platform.integrations.connectors.banks.stub_bank_connector import StubBankConnector
from app.modules.platform.integrations.services.connector_registry import connector_registry


def _make_provider_connector(provider_name: str) -> StubBankConnector:
    class ProviderConnector(StubBankConnector):
        pass

    ProviderConnector.provider_name = provider_name
    return ProviderConnector()


for _name in ("icici", "hdfc", "axis", "razorpayx", "yes_bank", "kotak"):
    connector_registry.register(_make_provider_connector(_name))
