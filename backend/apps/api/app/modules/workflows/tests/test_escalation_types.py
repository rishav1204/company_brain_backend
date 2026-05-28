from unittest.mock import MagicMock, patch

from app.modules.workflows.services.escalation_service import escalation_service


@patch("app.modules.workflows.services.escalation_service.emit_workflow_escalated")
@patch("app.modules.workflows.services.escalation_service.event_bus")
@patch("app.modules.workflows.services.escalation_service.workflow_repo")
@patch("app.modules.workflows.services.escalation_service.escalation_repo")
@patch("app.modules.workflows.services.escalation_service.workflow_orchestrator")
def test_finance_escalation_high_amount(
    mock_orch: MagicMock, mock_esc: MagicMock, mock_wf: MagicMock, mock_bus: MagicMock, mock_emit: MagicMock
) -> None:
    inst = {"id": "i1", "status": "waiting_approval", "metadata": {"amount": 250000}}
    mock_wf.list_instances.return_value = [inst]
    mock_wf.get_instance.return_value = inst
    mock_orch.resolve_assignee_for_role.return_value = "cfo-user"
    mock_esc.create_escalation.return_value = {"id": "e1"}
    out = escalation_service.process_finance_escalations("org-1")
    assert len(out) == 1
    assert mock_esc.create_escalation.call_args.kwargs["escalation_type"] == "finance_escalation"


@patch("app.modules.workflows.services.escalation_service.emit_workflow_escalated")
@patch("app.modules.workflows.services.escalation_service.event_bus")
@patch("app.modules.workflows.services.escalation_service.workflow_repo")
@patch("app.modules.workflows.services.escalation_service.escalation_repo")
@patch("app.modules.workflows.services.escalation_service.workflow_orchestrator")
def test_compliance_escalation_flags(
    mock_orch: MagicMock, mock_esc: MagicMock, mock_wf: MagicMock, mock_bus: MagicMock, mock_emit: MagicMock
) -> None:
    inst = {"id": "i2", "status": "running", "metadata": {"compliance_flags": ["gst_mismatch"]}}
    mock_wf.list_instances.return_value = [inst]
    mock_wf.get_instance.return_value = inst
    mock_orch.resolve_assignee_for_role.return_value = "comp-user"
    mock_esc.create_escalation.return_value = {"id": "e2"}
    out = escalation_service.process_compliance_escalations("org-1")
    assert len(out) == 1
    assert mock_esc.create_escalation.call_args.kwargs["escalation_type"] == "compliance_escalation"
