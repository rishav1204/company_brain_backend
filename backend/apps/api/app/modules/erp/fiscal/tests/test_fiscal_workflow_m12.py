from app.services.event_consumers import _handle_fiscal_workflow_approval


def test_fiscal_workflow_unknown_entity() -> None:
    assert _handle_fiscal_workflow_approval("org", {"entity_type": "other"}) is False
