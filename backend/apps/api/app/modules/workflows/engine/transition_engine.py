from app.modules.workflows.engine.workflow_state_machine import validate_transition


def apply_transition(*, current_status: str, target_status: str) -> str:
    validate_transition(current_status, target_status)
    return target_status.strip().lower()
