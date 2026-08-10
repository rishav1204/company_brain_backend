from __future__ import annotations

import os
from dataclasses import dataclass

from app.modules.platform.integrations.services.connector_registry import connector_registry
from app.core.config import settings


@dataclass(frozen=True)
class TdsConnectorConfig:
    nsdl_base_url: str
    nsdl_tan: str
    nsdl_user: str
    nsdl_password: str
    provider: str

    @property
    def nsdl_configured(self) -> bool:
        return bool(self.nsdl_base_url and self.nsdl_tan and self.nsdl_user and self.nsdl_password)


def load_tds_connector_config() -> TdsConnectorConfig:
    return TdsConnectorConfig(
        nsdl_base_url=os.getenv("NSDL_TDS_BASE_URL", "").strip(),
        nsdl_tan=os.getenv("NSDL_TDS_TAN", "").strip(),
        nsdl_user=os.getenv("NSDL_TDS_USER", "").strip(),
        nsdl_password=os.getenv("NSDL_TDS_PASSWORD", "").strip(),
        provider=os.getenv("TDS_CONNECTOR_PROVIDER", "auto").strip().lower(),
    )


def resolve_tds_filing_connector():
    cfg = load_tds_connector_config()
    if cfg.provider == "stub":
        conn = connector_registry.resolve(connector_type="tds", provider_name="stub_tds")
        if settings.app_env.lower() == "prod":
            raise RuntimeError("Production requires NSDL TDS credentials or TDS_CONNECTOR_PROVIDER=nsdl with NSDL_TDS_BASE_URL configured")
        return conn
    if cfg.nsdl_configured:
        conn = connector_registry.resolve(connector_type="tds", provider_name="nsdl_production")
        if conn:
            return conn
    conn = connector_registry.resolve(connector_type="tds", provider_name="stub_tds")
    if settings.app_env.lower() == "prod":
        raise RuntimeError("Production TDS filing requires NSDL credentials; stub connector is not allowed")
    return conn
