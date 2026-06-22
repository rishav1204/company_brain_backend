from __future__ import annotations

from datetime import datetime, timezone


DEFAULT_THRESHOLDS = [
    {"max_amount": 50000, "role": "manager"},
    {"max_amount": 500000, "role": "department_head"},
    {"max_amount": 2500000, "role": "controller"},
    {"max_amount": None, "role": "cfo"},
]


def _legacy_resolve_approval_chain(amount: float, thresholds: list[dict] | None = None) -> list[str]:
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


def resolve_approval_chain(amount: float, thresholds: list[dict] | None = None, *, org_id: str | None = None, action: str = "vendor_payment") -> list[str]:
    if org_id:
        from app.modules.platform.governance.engine import approval_engine

        chain = approval_engine.resolve_chain(org_id, action=action, amount=float(amount))
        if chain:
            return [str(c.get("role") or "") for c in chain if c.get("role")]
    return _legacy_resolve_approval_chain(amount, thresholds)


def workflow_metadata_for_amount(amount: float, *, thresholds: list[dict] | None = None, org_id: str | None = None) -> dict:
    return {
        "approval_chain": resolve_approval_chain(amount, thresholds, org_id=org_id),
        "amount": amount,
    }
