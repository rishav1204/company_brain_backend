from __future__ import annotations

from app.modules.workflows.engine.branch_resolver import (
    get_escalation_policies,
    get_retry_policy,
    resolve_execution_path,
)


def build_execution_plan(definition_json: dict | None, metadata: dict | None = None) -> dict:
    steps = resolve_execution_path(definition_json, metadata)
    return {
        "steps": steps,
        "step_count": len(steps),
        "escalation_policies": get_escalation_policies(definition_json),
        "assignment_strategy": (definition_json or {}).get("assignment_strategy", "load_balance"),
    }


def retry_policy_for_step(step_def: dict, definition_json: dict | None) -> dict:
    return get_retry_policy(step_def, definition_json)
