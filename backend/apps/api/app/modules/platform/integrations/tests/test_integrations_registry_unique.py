from __future__ import annotations

from app.modules.platform.integrations.services.connector_registry import connector_registry


def test_registry_lists_connectors() -> None:
    items = connector_registry.list()
    assert isinstance(items, list)
