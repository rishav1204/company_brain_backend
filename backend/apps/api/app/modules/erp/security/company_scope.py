from __future__ import annotations

from app.modules.core.iam.services.branch_scope_service import evaluate_branch_scope


def require_company_id_for_erp_write(
    *,
    org_id: str,
    company_id: str | None,
    operation: str,
    attrs: dict | None = None,
) -> str:
    """ERP transactional writes must be scoped to a company when multi-entity is enabled."""
    normalized = str(company_id or "").strip()
    if not normalized:
        raise ValueError(f"company_id is required for ERP operation: {operation} (org_id={org_id})")
    scope_decision = evaluate_branch_scope(
        attrs=attrs,
        object_branch_id=None,
        object_company_id=normalized,
    )
    if scope_decision and not scope_decision.allowed:
        raise ValueError(scope_decision.reason or "company_scope_denied")
    return normalized
