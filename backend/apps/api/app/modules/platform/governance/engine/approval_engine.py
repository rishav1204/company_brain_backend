from __future__ import annotations

from app.modules.platform.governance.repositories.approval_matrix_repository import approval_matrix_repository
from app.modules.platform.governance.engine import policy_cache_engine


def _normalize_action(action: str) -> str:
    mapping = {
        "approve_payment": "payment.execute",
        "payment.approve": "payment.execute",
        "post_journal": "journal.post",
        "journal.post": "journal.post",
    }
    return mapping.get(action, action)


def load_matrix(org_id: str, action_code: str, *, company_id: str | None = None) -> list[dict]:
    cached = policy_cache_engine.get_cached(org_id, "matrix")
    cache_key = _normalize_action(action_code)
    if cached is not None and isinstance(cached, dict):
        rows = cached.get(cache_key) or cached.get(action_code) or []
        if company_id:
            scoped = [r for r in rows if not r.get("company_id") or str(r.get("company_id")) == str(company_id)]
            if scoped:
                return scoped
        return rows
    rows = approval_matrix_repository.list_active(
        org_id, action_code=_normalize_action(action_code), company_id=company_id
    )
    if not rows:
        rows = approval_matrix_repository.list_active(org_id, action_code=action_code)
    all_matrix: dict[str, list] = {}
    if approval_matrix_repository.schema_ready():
        for code in {_normalize_action(action_code), action_code, "vendor_payment", "payment.execute"}:
            all_matrix[code] = approval_matrix_repository.list_active(org_id, action_code=code)
    policy_cache_engine.set_cached(org_id, "matrix", all_matrix)
    return all_matrix.get(_normalize_action(action_code)) or rows


def resolve_chain(
    org_id: str,
    *,
    action: str,
    amount: float,
    department: str | None = None,
    company_id: str | None = None,
) -> list[dict]:
    rows = load_matrix(org_id, action, company_id=company_id)
    if not rows:
        return []
    amt = float(amount)
    chain: list[dict] = []
    for row in rows:
        try:
            min_amt = float(row.get("min_amount") or 0)
            max_amt = row.get("max_amount")
            max_val = float(max_amt) if max_amt is not None else float("inf")
        except (TypeError, ValueError):
            continue
        if dept := row.get("department"):
            if department and str(dept) != str(department):
                continue
        if amt >= min_amt and amt < max_val:
            chain.append({"level": int(row.get("level") or 1), "role": str(row.get("approver_role") or "")})
        elif amt >= min_amt and max_amt is None:
            chain.append({"level": int(row.get("level") or 1), "role": str(row.get("approver_role") or "")})
    if not chain and rows:
        for row in rows:
            chain.append({"level": int(row.get("level") or 1), "role": str(row.get("approver_role") or "")})
            break
    return [c for c in chain if c.get("role")]


def required_roles_missing(chain: list[dict], roles: list[str]) -> list[str]:
    role_set = {r.lower() for r in roles}
    elevated = {"tenant_admin", "finance_admin", "governance_admin", "admin"}
    if role_set & elevated:
        return []
    required = [str(c.get("role") or "").lower() for c in chain if c.get("role")]
    return [r for r in required if r not in role_set and r != "dual_approval"]


def to_legacy_payment_policy(amount: float, payment_type: str, chain: list[dict]) -> dict:
    roles = [c["role"] for c in chain if c.get("role")]
    amt = float(amount)
    if not roles:
        roles = ["finance_manager"]
        if amt >= 50_000:
            roles.append("controller")
        if amt >= 500_000:
            roles.append("cfo")
        if amt >= 2_500_000:
            roles.append("dual_approval")
    if payment_type in {"tax_payment", "internal_transfer"} and amt >= 100_000 and "cfo" not in roles:
        roles.append("cfo")
    return {
        "amount": amt,
        "payment_type": payment_type,
        "required_roles": roles,
        "requires_controller": amt >= 50_000,
        "requires_cfo": amt >= 500_000,
        "requires_dual": amt >= 2_500_000 or "dual_approval" in roles,
    }
