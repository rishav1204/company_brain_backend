from __future__ import annotations

from app.modules.workflows.engine.workflow_state_machine import can_transition


def validate_transition_request(current_status: str, target_status: str) -> None:
    if not can_transition(current_status, target_status):
        from app.modules.workflows.engine.workflow_state_machine import InvalidTransitionError

        raise InvalidTransitionError(current_status, target_status)


def validate_start_request(*, workflow_key: str | None, workflow_type: str | None) -> None:
    if not workflow_key and not workflow_type:
        raise ValueError("workflow_key or workflow_type is required")
