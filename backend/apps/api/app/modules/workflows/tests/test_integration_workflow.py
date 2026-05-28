from unittest.mock import MagicMock, patch

from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created


@patch("app.modules.workflows.services.erp_workflow_consumer.workflow_service")
def test_erp_invoice_created_starts_workflow(mock_svc: MagicMock) -> None:
    mock_svc.schema_ready.return_value = True
    mock_svc.start_workflow.return_value = {"id": "wf-1", "status": "running"}
    result = handle_entity_created(
        org_id="11111111-1111-4111-8111-111111111111",
        payload={"entity_type": "invoice", "entity_id": "inv-1", "amount": 25000},
    )
    assert result["id"] == "wf-1"
    mock_svc.start_workflow.assert_called_once()
    assert mock_svc.start_workflow.call_args.kwargs["workflow_key"] == "AP_INVOICE_APPROVAL"
