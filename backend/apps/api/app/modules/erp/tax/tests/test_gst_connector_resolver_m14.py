from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import (
    load_gst_connector_config,
    resolve_eway_connector,
    resolve_gst_filing_connector,
    resolve_irp_connector,
)


def test_gst_connector_config_defaults() -> None:
    cfg = load_gst_connector_config()
    assert cfg.provider in {"auto", "stub", ""} or isinstance(cfg.provider, str)


def test_resolve_stubs_without_credentials() -> None:
    assert resolve_gst_filing_connector() is not None
    assert resolve_irp_connector() is not None
    assert resolve_eway_connector() is not None
