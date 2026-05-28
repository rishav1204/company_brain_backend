from app.modules.core.iam.services.abac_service import evaluate_amount_limit
from app.modules.core.iam.services.identity_resolver import resolve_user_id
from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.core.iam.services.rbac_service import has_permission
from app.services.object_context import ObjectContext
from app.services.policy_service import PolicyDecision, evaluate_object_permission


def evaluate_iam_permission(
    *,
    org_id: str,
    user_id: str,
    roles: list[str],
    permission_key: str,
    action: str,
    object_context: ObjectContext,
    attrs: dict | None = None,
    actor_user_id: str | None = None,
    created_by: str | None = None,
    human_approved: bool = False,
) -> PolicyDecision:
    checks: list[str] = ["iam_rbac_checked"]
    if permission_key:
        if not has_permission(org_id, user_id, permission_key):
            return PolicyDecision(allowed=False, reason="missing_permission", checks=checks + ["permission_denied"])
        checks.append("permission_granted")

    if created_by:
        try:
            enforce_maker_checker(
                created_by=resolve_user_id(org_id, created_by) or created_by,
                actor_user_id=resolve_user_id(org_id, actor_user_id or user_id) or (actor_user_id or user_id),
                org_id=org_id,
            )
            checks.append("maker_checker_passed")
        except MakerCheckerViolation as exc:
            return PolicyDecision(allowed=False, reason=str(exc), checks=checks + ["maker_checker_denied"])

    amount_decision = evaluate_amount_limit(attrs, object_context.amount)
    if amount_decision is not None:
        return amount_decision

    from app.modules.core.iam.services.approval_gate_service import requires_human_approval

    if requires_human_approval(
        action=action,
        amount=object_context.amount,
        vendor_risk=object_context.vendor_risk,
        attrs=attrs,
    ) and not human_approved:
        return PolicyDecision(allowed=False, reason="human_approval_required", checks=checks + ["approval_required"])

    return evaluate_object_permission(
        roles=roles,
        action=action,
        object_context=object_context,
        attrs=attrs,
        actor_user_id=actor_user_id or user_id,
        human_approved=human_approved,
    )
