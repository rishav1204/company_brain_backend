from __future__ import annotations

from typing import Any


def build_approval_chain(definition: dict | None, metadata: dict | None) -> list[dict[str, Any]]:
    """Build ordered approval levels from thresholds, approval_chain, and metadata."""
    definition = definition or {}
    metadata = metadata or {}
    amount = metadata.get("amount")
    try:
        amount_f = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_f = None

    org_id = metadata.get("org_id")
    action_code = str(metadata.get("action_code") or definition.get("action_code") or "vendor_payment")
    if org_id and amount_f is not None:
        from app.modules.platform.governance.engine import approval_engine

        matrix_chain = approval_engine.resolve_chain(
            str(org_id),
            action=action_code,
            amount=amount_f,
            department=metadata.get("department"),
        )
        if matrix_chain:
            return [{"level": int(c.get("level") or idx + 1), "role": str(c.get("role") or "")} for idx, c in enumerate(matrix_chain) if c.get("role")]

    explicit = definition.get("approval_chain")
    if isinstance(explicit, list) and explicit:
        chain: list[dict[str, Any]] = []
        for idx, row in enumerate(explicit):
            if not isinstance(row, dict):
                continue
            chain.append({"level": int(row.get("level") or idx + 1), "role": str(row.get("role") or "")})
        return [r for r in chain if r.get("role")]

    thresholds = definition.get("thresholds")
    if isinstance(thresholds, list) and thresholds and amount_f is not None:
        sorted_rows = []
        for row in thresholds:
            if not isinstance(row, dict):
                continue
            max_amount = row.get("max_amount")
            try:
                cap = float(max_amount) if max_amount is not None else float("inf")
            except (TypeError, ValueError):
                cap = float("inf")
            sorted_rows.append((cap, str(row.get("role") or "")))
        sorted_rows.sort(key=lambda x: x[0])
        target_idx = len(sorted_rows) - 1
        for idx, (cap, role) in enumerate(sorted_rows):
            if amount_f <= cap:
                target_idx = idx
                break
        chain = []
        for idx in range(target_idx + 1):
            role = sorted_rows[idx][1]
            if role:
                chain.append({"level": idx + 1, "role": role})
        if chain:
            return chain

    default_role = definition.get("default_approver_role") or "finance_manager"
    return [{"level": 1, "role": str(default_role)}]


def inject_conditional_approvers(chain: list[dict], definition: dict | None, metadata: dict | None) -> list[dict]:
    definition = definition or {}
    metadata = metadata or {}
    rules = definition.get("conditional_approvals")
    if not isinstance(rules, list):
        return chain
    extra: list[dict] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        from app.modules.workflows.engine.condition_evaluator import evaluate_condition

        if evaluate_condition(rule.get("when"), metadata):
            role = str(rule.get("role") or "")
            if role:
                extra.append({"level": 0, "role": role, "conditional": True})
    if not extra:
        return chain
    merged = extra + chain
    for idx, row in enumerate(merged, start=1):
        row["level"] = idx
    return merged
