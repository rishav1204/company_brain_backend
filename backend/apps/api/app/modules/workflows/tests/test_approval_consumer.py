from unittest.mock import MagicMock, patch

from app.services.event_consumers import _consume_workflow_approval_event


@patch("app.modules.workflows.services.workflow_orchestrator.workflow_orchestrator")
@patch("app.modules.workflows.repositories.workflow_repo.get_instance")
def test_workflow_approval_consumer_advances(mock_get: MagicMock, mock_orch: MagicMock) -> None:
    mock_get.return_value = {"id": "inst-1", "status": "executing"}
    mock_orch.advance_after_approval.return_value = {"status": "completed"}
    result = _consume_workflow_approval_event(
        {
            "org_id": "org-1",
            "event_type": "workflow.advance.requested",
            "payload": {"workflow_instance_id": "inst-1", "decided_level": 1},
        }
    )
    assert result["status"] == "completed"
    mock_orch.advance_after_approval.assert_called_once()
