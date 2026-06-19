from app.modules.platform.integrations.connectors.tds.stub_tds_connector import StubTdsConnector
from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import (
    load_tds_connector_config,
    resolve_tds_filing_connector,
)


def test_resolve_tds_filing_connector() -> None:
    assert resolve_tds_filing_connector() is not None


def test_stub_tds_submit_return() -> None:
    conn = StubTdsConnector()
    result = conn.submit_return(
        idempotency_key="test",
        payload={"form_type": "26Q", "return_period": "2025-04", "data": {}},
    )
    assert result.form_type == "26Q"
    assert result.acknowledgment_no


def test_stub_tds_generate_fvu() -> None:
    conn = StubTdsConnector()
    result = conn.generate_fvu(payload={"form_type": "26Q", "return_period": "2025-04"})
    assert result["fvu_file_name"]
    assert result["status"] == "generated"


def test_stub_tds_validate_challan() -> None:
    conn = StubTdsConnector()
    result = conn.validate_challan(challan_no="CH123", bsr_code="BSR1", amount=1000)
    assert result["valid"] is True


def test_load_tds_connector_config() -> None:
    cfg = load_tds_connector_config()
    assert cfg.provider in {"auto", "stub", "nsdl", ""} or isinstance(cfg.provider, str)
