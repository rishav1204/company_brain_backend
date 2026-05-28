import pytest

from app.modules.workflows.engine.workflow_state_machine import (
    InvalidTransitionError,
    can_transition,
    legacy_state_to_status,
    status_to_legacy_state,
    validate_transition,
)


def test_allowed_transition_draft_to_queued() -> None:
    assert can_transition("draft", "queued")
    validate_transition("draft", "queued")


def test_disallowed_transition_completed_to_running() -> None:
    assert not can_transition("completed", "running")
    with pytest.raises(InvalidTransitionError):
        validate_transition("completed", "running")


def test_legacy_mapping_roundtrip() -> None:
    assert legacy_state_to_status("pending_approval") == "waiting_approval"
    assert status_to_legacy_state("waiting_approval") == "pending_approval"
