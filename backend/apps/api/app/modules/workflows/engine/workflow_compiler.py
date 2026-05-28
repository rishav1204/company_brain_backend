"""Compile workflow definition JSON into execution plan."""

from __future__ import annotations


def compile_definition(definition_json: dict | None) -> list[dict]:
    definition = definition_json or {}
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return []
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
            }
        )
    return plan


def resolve_threshold_role(definition_json: dict | None, amount: float | None) -> str | None:
    if amount is None:
        return None
    definition = definition_json or {}
    thresholds = definition.get("thresholds")
    if not isinstance(thresholds, list):
        return None
    sorted_thresholds = []
    for row in thresholds:
        if not isinstance(row, dict):
            continue
        max_amount = row.get("max_amount")
        if max_amount is None:
            sorted_thresholds.append((float("inf"), str(row.get("role"))))
        else:
            try:
                sorted_thresholds.append((float(max_amount), str(row.get("role"))))
            except (TypeError, ValueError):
                continue
    sorted_thresholds.sort(key=lambda x: x[0])
    for limit, role in sorted_thresholds:
        if amount <= limit:
            return role
    return None
