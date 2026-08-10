from __future__ import annotations

import os
from datetime import datetime

from app.core.config import settings
from app.modules.platform.integrations.services.connector_registry import connector_registry


def resolve_bank_connector(provider: str | None = None):
    configured = (provider or os.getenv("BANK_CONNECTOR_PROVIDER", "stub_bank")).strip()
    if settings.app_env.lower() == "prod":
        if configured in {"", "stub_bank", "stub"}:
            if os.getenv("BANK_API_BASE_URL", "").strip():
                configured = "http_bank"
            else:
                raise RuntimeError("Production requires BANK_CONNECTOR_PROVIDER=http_bank with BANK_API_BASE_URL")
    if configured in {"http_bank", "production"}:
        conn = connector_registry.resolve(connector_type="bank", provider_name="http_bank")
        if conn:
            return conn
    conn = connector_registry.resolve(connector_type="bank", provider_name=configured)
    if conn is None:
        conn = connector_registry.resolve(connector_type="bank", provider_name="stub_bank")
    return conn
