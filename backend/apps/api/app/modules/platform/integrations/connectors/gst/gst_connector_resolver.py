from __future__ import annotations

import os
from dataclasses import dataclass

from app.modules.platform.integrations.services.connector_registry import connector_registry


@dataclass(frozen=True)
class GstConnectorConfig:
    gstn_base_url: str
    gstn_username: str
    gstn_password: str
    gstn_api_key: str
    irp_base_url: str
    irp_client_id: str
    irp_client_secret: str
    eway_base_url: str
    eway_username: str
    eway_password: str
    provider: str

    @property
    def gstn_configured(self) -> bool:
        return bool(self.gstn_base_url and (self.gstn_api_key or (self.gstn_username and self.gstn_password)))

    @property
    def irp_configured(self) -> bool:
        return bool(self.irp_base_url and self.irp_client_id and self.irp_client_secret)

    @property
    def eway_configured(self) -> bool:
        return bool(self.eway_base_url and self.eway_username and self.eway_password)


def load_gst_connector_config() -> GstConnectorConfig:
    return GstConnectorConfig(
        gstn_base_url=os.getenv("GSTN_BASE_URL", "").strip(),
        gstn_username=os.getenv("GSTN_USERNAME", "").strip(),
        gstn_password=os.getenv("GSTN_PASSWORD", "").strip(),
        gstn_api_key=os.getenv("GSTN_API_KEY", "").strip(),
        irp_base_url=os.getenv("IRP_BASE_URL", "").strip(),
        irp_client_id=os.getenv("IRP_CLIENT_ID", "").strip(),
        irp_client_secret=os.getenv("IRP_CLIENT_SECRET", "").strip(),
        eway_base_url=os.getenv("EWAY_BASE_URL", "").strip(),
        eway_username=os.getenv("EWAY_USERNAME", "").strip(),
        eway_password=os.getenv("EWAY_PASSWORD", "").strip(),
        provider=os.getenv("GST_CONNECTOR_PROVIDER", "auto").strip().lower(),
    )


def resolve_gst_filing_connector():
    cfg = load_gst_connector_config()
    if cfg.provider == "stub":
        return connector_registry.resolve(connector_type="gst", provider_name="stub_gst")
    if cfg.gstn_configured:
        conn = connector_registry.resolve(connector_type="gst", provider_name="gstn_production")
        if conn:
            return conn
        conn = connector_registry.resolve(connector_type="gst", provider_name="gstn")
    return connector_registry.resolve(connector_type="gst", provider_name="stub_gst")


def resolve_irp_connector():
    cfg = load_gst_connector_config()
    if cfg.provider == "stub":
        return connector_registry.resolve(connector_type="irp", provider_name="gstn_irp")
    if cfg.irp_configured:
        conn = connector_registry.resolve(connector_type="irp", provider_name="irp_production")
        if conn:
            return conn
    conn = connector_registry.resolve(connector_type="irp", provider_name="gstn_irp")
    if conn:
        return conn
    return connector_registry.resolve(connector_type="gst", provider_name="stub_gst")


def resolve_eway_connector():
    cfg = load_gst_connector_config()
    if cfg.provider == "stub":
        return connector_registry.resolve(connector_type="eway", provider_name="stub_eway")
    if cfg.eway_configured:
        conn = connector_registry.resolve(connector_type="eway", provider_name="eway_production")
        if conn:
            return conn
    conn = connector_registry.resolve(connector_type="eway", provider_name="stub_eway")
    if conn:
        return conn
    return connector_registry.resolve(connector_type="gst", provider_name="stub_gst")
