from __future__ import annotations

from typing import Any

from app.modules.workflows.engine.condition_evaluator import evaluate_condition, step_should_run


def resolve_execution_path(definition: dict | None, metadata: dict | None) -> list[dict]:
    """Resolve linear or branched step list from definition JSON."""
    definition = definition or {}
    metadata = metadata or {}
    branches = definition.get("branches")
    if isinstance(branches, list) and branches:
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            when = branch.get("when")
            if when is None or evaluate_condition(when, metadata):
                steps = branch.get("steps")
                if isinstance(steps, list):
                    return _normalize_steps(steps)
    steps = definition.get("steps")
    if isinstance(steps, list):
        return [s for s in _normalize_steps(steps) if step_should_run(s, metadata)]
    return []


def _normalize_steps(steps: list) -> list[dict]:
    plan: list[dict] = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        plan.append(
            {
                "order": idx,
                "key": str(step.get("key") or f"step_{idx}"),
                "type": str(step.get("type") or "system_task"),
                "optional": bool(step.get("optional")),
                "sla_hours": step.get("sla_hours"),
                "conditions": step.get("conditions") or {},
                "retry": step.get("retry") or {},
                "assignment_strategy": step.get("assignment_strategy"),
            }
        )
    return plan


def get_escalation_policies(definition: dict | None) -> list[dict]:
    definition = definition or {}
    policies = definition.get("escalation_policies")
    if isinstance(policies, list):
        return [p for p in policies if isinstance(p, dict)]
    return []


def get_retry_policy(step_def: dict, definition: dict | None) -> dict:
    step_retry = step_def.get("retry") if isinstance(step_def.get("retry"), dict) else {}
    definition = definition or {}
    default = definition.get("retry_policy")
    base = dict(default) if isinstance(default, dict) else {}
    base.update(step_retry)
    return base
