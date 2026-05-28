from unittest.mock import MagicMock, patch

from app.modules.platform.events.events.erp_events import emit_invoice_created


@patch("app.modules.platform.events.events.erp_events.platform_event_service")
def test_emit_invoice_created(mock_svc: MagicMock) -> None:
    mock_svc.publish.return_value = {"event_id": "e1", "event_type": "erp.invoice.created"}
    result = emit_invoice_created(
        "11111111-1111-4111-8111-111111111111",
        invoice_id="inv-1",
        amount=5000,
        idempotency_key="key-1",
    )
    assert result["event_id"] == "e1"
    mock_svc.publish.assert_called_once()
    assert mock_svc.publish.call_args.kwargs["event_type"] == "erp.invoice.created"
    assert mock_svc.publish.call_args.kwargs["source"] == "erp.ap"
