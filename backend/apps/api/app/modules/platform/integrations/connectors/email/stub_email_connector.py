from __future__ import annotations

from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubEmailConnector:
    connector_type = "email"
    provider_name = "stub"

    def health(self) -> dict:
        return {"ready": True}


connector_registry.register(StubEmailConnector())

