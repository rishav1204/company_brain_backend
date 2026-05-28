from __future__ import annotations

from typing import Any


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def evaluate_condition(condition: dict | None, metadata: dict | None) -> bool:
    if not condition:
        return True
    meta = metadata or {}
    for key, expected in condition.items():
        actual = meta.get(key)
        if isinstance(expected, dict):
            op = expected.get("op", "eq")
            val = expected.get("value")
            if op == "eq" and _normalize(actual) != _normalize(val):
                return False
            if op == "neq" and _normalize(actual) == _normalize(val):
                return False
            if op == "in":
                allowed = {_normalize(v) for v in (val or [])}
                if _normalize(actual) not in allowed:
                    return False
            if op == "gte":
                try:
                    if float(actual) < float(val):
                        return False
                except (TypeError, ValueError):
                    return False
            if op == "lte":
                try:
                    if float(actual) > float(val):
                        return False
                except (TypeError, ValueError):
                    return False
        else:
            if _normalize(actual) != _normalize(expected):
                return False
    return True


def step_should_run(step_def: dict, metadata: dict | None) -> bool:
    conditions = step_def.get("conditions")
    if conditions is None:
        return True
    if isinstance(conditions, list):
        return all(evaluate_condition(c, metadata) if isinstance(c, dict) else True for c in conditions)
    if isinstance(conditions, dict):
        return evaluate_condition(conditions, metadata)
    return True
