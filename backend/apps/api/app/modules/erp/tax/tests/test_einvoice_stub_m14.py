from app.modules.platform.integrations.connectors.gst.stub_gst_connector import StubGstConnector


def test_stub_generate_irn() -> None:
    connector = StubGstConnector()
    result = connector.generate_irn(idempotency_key="inv-1", payload={"invoice_number": "INV-001"})
    assert result["irn"].startswith("IRN")
    assert result["ack_no"]


def test_stub_eway_bill() -> None:
    connector = StubGstConnector()
    result = connector.generate_eway_bill(idempotency_key="ship-1", payload={})
    assert result["eway_bill_no"].startswith("EWB")
