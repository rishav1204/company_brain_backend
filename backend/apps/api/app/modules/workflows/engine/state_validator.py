from app.modules.workflows.engine.workflow_state_machine import validate_transition


def validate_status_change(*, current: str, target: str) -> None:
    validate_transition(current, target)
