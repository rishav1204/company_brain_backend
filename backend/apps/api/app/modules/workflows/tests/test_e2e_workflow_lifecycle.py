from unittest.mock import MagicMock, patch

from app.modules.workflows.services.approval_service import approval_service
from app.modules.workflows.services.step_executors import execute_step


@patch("app.modules.workflows.services.approval_service.resolve_object_context")
@patch("app.modules.workflows.services.approval_service.workflow_orchestrator")
@patch("app.modules.workflows.services.approval_service.workflow_uow")
@patch("app.modules.workflows.services.approval_service.approval_repo")
@patch("app.modules.workflows.services.approval_service.workflow_repo")
@patch("app.modules.workflows.services.approval_service.validate_approval_authority")
def test_approve_publishes_advance_and_returns_status(
    mock_auth: MagicMock,
    mock_wf: MagicMock,
    mock_appr: MagicMock,
    mock_uow: MagicMock,
    mock_orch: MagicMock,
    mock_ctx: MagicMock,
) -> None:
    mock_auth.return_value = (True, None)
    mock_ctx.return_value = MagicMock()
    mock_appr.get_approval.return_value = {
        "id": "a1",
        "decision": "pending",
        "workflow_instance_id": "i1",
        "workflow_step_id": "s1",
        "level": 1,
        "created_at": None,
    }
    mock_wf.get_instance.return_value = {"id": "i1", "status": "waiting_approval", "metadata": {}}
    uow = MagicMock()
    uow.__enter__ = MagicMock(return_value=uow)
    uow.__exit__ = MagicMock(return_value=False)
    uow.decide_approval.return_value = {
        "id": "a1",
        "decision": "approved",
        "workflow_instance_id": "i1",
        "workflow_step_id": "s1",
        "level": 1,
    }
    mock_uow.return_value = uow
    mock_orch.advance_after_approval.return_value = {"status": "executing"}

    with (
        patch("app.modules.workflows.services.approval_service.emit_approval_completed"),
        patch("app.modules.workflows.services.approval_service.emit_workflow_advance_requested"),
        patch("app.modules.workflows.services.approval_service.audit_transition"),
        patch("app.services.event_consumers._consume_workflow_approval_event") as mock_consume,
    ):
        mock_consume.return_value = {"status": "executing"}
        row = approval_service.decide(
            org_id="org-1",
            user_id="u1",
            roles=["finance_manager"],
            attrs={},
            approval_id="a1",
            decision="approved",
        )
    assert row["workflow_status"] == "executing"


@patch("app.modules.workflows.services.step_executors.event_bus")
@patch("app.modules.workflows.services.step_executors.audit_repo")
def test_ai_review_waits_for_agent(mock_audit: MagicMock, mock_bus: MagicMock) -> None:
    result = execute_step(
        org_id="org-1",
        instance={"id": "i1", "metadata": {}},
        step={"id": "s-ai", "step_type": "ai_review"},
    )
    assert result["status"] == "waiting_ai"
    mock_bus.publish.assert_called_once()
