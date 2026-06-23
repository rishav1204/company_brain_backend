"""Integration connector mode — stub vs production selection."""
from __future__ import annotations

from app.core.config import settings


def integrations_use_stubs() -> bool:
    return settings.integrations_use_stubs()


def require_production_connector(connector_type: str, provider_name: str) -> None:
    if integrations_use_stubs():
        return
    if provider_name.startswith("stub") or "stub" in provider_name:
        raise RuntimeError(
            f"Stub connector {connector_type}/{provider_name} disabled when INTEGRATIONS_MODE=production"
        )
