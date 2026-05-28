from concurrent.futures import ThreadPoolExecutor

from app.modules.workflows.engine.workflow_state_machine import can_transition, validate_transition


def _transition_once() -> bool:
    validate_transition("draft", "queued")
    validate_transition("queued", "running")
    validate_transition("running", "waiting_approval")
    validate_transition("waiting_approval", "approved")
    validate_transition("approved", "executing")
    validate_transition("executing", "completed")
    return can_transition("completed", "running") is False


def test_concurrent_fsm_transitions() -> None:
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: _transition_once(), range(500)))
    assert all(results)
