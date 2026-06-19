from __future__ import annotations

from datetime import datetime, timezone


DEFAULT_THRESHOLDS = [
    {"max_amount": 50000, "role": "manager"},
    {"max_amount": 500000, "role": "department_head"},
    {"max_amount": 2500000, "role": "controller"},
    {"max_amount": None, "role": "cfo"},
]


def resolve_approval_chain(amount: float, thresholds: list[dict] | None = None) -> list[str]:
    chain: list[str] = []
    for step in thresholds or DEFAULT_THRESHOLDS:
        max_amt = step.get("max_amount")
        role = str(step.get("role") or "")
        if not role:
            continue
        if max_amt is None or amount <= float(max_amt):
            chain.append(role)
            break
        chain.append(role)
    return chain or ["manager"]


def workflow_metadata_for_amount(amount: float, *, thresholds: list[dict] | None = None) -> dict:
    return {
        "approval_chain": resolve_approval_chain(amount, thresholds),
        "amount": amount,
    }
