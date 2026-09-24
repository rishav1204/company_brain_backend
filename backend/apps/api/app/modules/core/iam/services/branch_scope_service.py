from app.services.policy_service import PolicyDecision


def evaluate_branch_scope(
    *,
    attrs: dict | None,
    object_branch_id: str | None,
    object_company_id: str | None,
    object_department_id: str | None = None,
) -> PolicyDecision | None:
    """Enforce ABAC scope when the target object has a concrete branch/company/dept.

    List/inbox endpoints often omit object scope (None). In that case do not deny —
    callers filter by allowed_* ids at query time. Deny only when an object id is set
    and falls outside the caller's allowed set.
    """
    attrs = attrs or {}
    allowed_branches = attrs.get("allowed_branch_ids")
    allowed_companies = attrs.get("allowed_company_ids")
    allowed_departments = attrs.get("allowed_department_ids")
    if isinstance(allowed_branches, list) and allowed_branches and object_branch_id:
        if str(object_branch_id) not in {str(b) for b in allowed_branches}:
            return PolicyDecision(
                allowed=False,
                reason="branch_scope_denied",
                checks=["branch_abac_denied"],
            )
    if isinstance(allowed_companies, list) and allowed_companies and object_company_id:
        if str(object_company_id) not in {str(c) for c in allowed_companies}:
            return PolicyDecision(
                allowed=False,
                reason="company_scope_denied",
                checks=["company_abac_denied"],
            )
    if isinstance(allowed_departments, list) and allowed_departments and object_department_id:
        if str(object_department_id) not in {str(d) for d in allowed_departments}:
            return PolicyDecision(
                allowed=False,
                reason="department_scope_denied",
                checks=["department_abac_denied"],
            )
    return None
