from app.services.policy_service import PolicyDecision


def evaluate_branch_scope(
    *,
    attrs: dict | None,
    object_branch_id: str | None,
    object_company_id: str | None,
) -> PolicyDecision | None:
    attrs = attrs or {}
    allowed_branches = attrs.get("allowed_branch_ids")
    allowed_companies = attrs.get("allowed_company_ids")
    if isinstance(allowed_branches, list) and allowed_branches:
        if not object_branch_id or str(object_branch_id) not in {str(b) for b in allowed_branches}:
            return PolicyDecision(
                allowed=False,
                reason="branch_scope_denied",
                checks=["branch_abac_denied"],
            )
    if isinstance(allowed_companies, list) and allowed_companies:
        if not object_company_id or str(object_company_id) not in {str(c) for c in allowed_companies}:
            return PolicyDecision(
                allowed=False,
                reason="company_scope_denied",
                checks=["company_abac_denied"],
            )
    return None
