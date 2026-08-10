"""Context boundary enforcement — scope isolation for retrieval and tool results (AI-17)."""

from __future__ import annotations

from typing import Any

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState
from app.services.logger import log_event


class ContextBoundaryViolation(PermissionError):
    """Raised when a retrieval or result row falls outside the session scope."""


def session_scope(org_id: str, world_state: WorldState | None, attrs: dict | None) -> dict[str, Any]:
    attrs = attrs or {}
    org = world_state.org if world_state else None
    return {
        "organization_id": org_id,
        "company_id": (org.company_id if org else None) or attrs.get("company_id"),
        "branch_id": (org.branch_id if org else None) or attrs.get("branch_id"),
        "allowed_branch_ids": list(attrs.get("allowed_branch_ids") or [])
        or ([org.branch_id] if org and org.branch_id else []),
        "department_id": attrs.get("department_id"),
        "fiscal_period_id": (org.fiscal_period_id if org else None) or attrs.get("fiscal_period_id"),
        "permissions": list(getattr(world_state, "permissions", None) or attrs.get("permissions") or []),
        "screen": world_state.screen.model_dump() if world_state and world_state.screen else {},
    }


def assert_org_matches(requested_org: str, session_org: str) -> None:
    if not requested_org or not session_org or str(requested_org) != str(session_org):
        raise ContextBoundaryViolation("organization scope mismatch")


def row_in_scope(row: dict, scope: dict[str, Any]) -> bool:
    """Return False if row clearly belongs to another branch/company within org."""
    if not isinstance(row, dict):
        return True
    # Hard block foreign org markers if present on row
    row_org = row.get("org_id") or row.get("organization_id")
    if row_org and scope.get("organization_id") and str(row_org) != str(scope["organization_id"]):
        return False
    allowed_branches = {str(b) for b in (scope.get("allowed_branch_ids") or []) if b}
    branch = row.get("branch_id")
    if branch and allowed_branches and str(branch) not in allowed_branches:
        return False
    company = row.get("company_id")
    scope_company = scope.get("company_id")
    if company and scope_company and str(company) != str(scope_company):
        return False
    return True


def filter_result_payload(result: Any, scope: dict[str, Any]) -> Any:
    """Post-filter list/dict tool results for branch/company isolation (AI-17)."""
    if isinstance(result, list):
        filtered = [r for r in result if not isinstance(r, dict) or row_in_scope(r, scope)]
        dropped = len(result) - len(filtered)
        if dropped:
            log_event(
                "m38.security.scope_filter",
                dropped=dropped,
                org_id=str(scope.get("organization_id") or ""),
            )
        return filtered
    if isinstance(result, dict):
        if "items" in result and isinstance(result["items"], list):
            return {**result, "items": filter_result_payload(result["items"], scope)}
        if not row_in_scope(result, scope):
            log_event(
                "m38.security.scope_filter_row_blocked",
                org_id=str(scope.get("organization_id") or ""),
            )
            return {"status": "error", "detail": "out_of_scope", "retryable": False}
        return result
    return result


def enforce_retrieval_params(
    payload: dict,
    *,
    org_id: str,
    world_state: WorldState | None,
    attrs: dict | None,
) -> dict:
    """UI context influences ranking params only; never override session org or expand scope."""
    scope = session_scope(org_id, world_state, attrs)
    safe = dict(payload or {})
    # Strip any LLM/user-injected tenancy keys
    for bad in ("org_id", "organization_id", "human_approved", "roles", "permissions"):
        safe.pop(bad, None)
    if scope.get("company_id") and not safe.get("company_id"):
        safe["company_id"] = scope["company_id"]
    if scope.get("branch_id") and not safe.get("branch_id"):
        safe["branch_id"] = scope["branch_id"]
    if scope.get("allowed_branch_ids") and not safe.get("branch_ids"):
        safe["branch_ids"] = list(scope["allowed_branch_ids"])
    if scope.get("fiscal_period_id") and not safe.get("period_id"):
        safe["period_id"] = scope["fiscal_period_id"]
    return safe
