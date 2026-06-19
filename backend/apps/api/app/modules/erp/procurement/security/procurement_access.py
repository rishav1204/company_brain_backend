from __future__ import annotations

from app.api.deps import RequestContext
from app.modules.core.iam.services.access_control import evaluate_access


PROCUREMENT_ADMIN_ROLES = {"procurement_manager", "buyer", "cfo", "controller", "finance_manager", "tenant_admin", "ap_manager"}
PROCUREMENT_READ_ROLES = PROCUREMENT_ADMIN_ROLES | {"requester", "auditor", "analyst"}


def enforce_procurement_action(
    context: RequestContext,
    *,
    action: str,
    object_type: str = "procurement",
    object_id: str = "",
    amount: float | None = None,
    company_id: str | None = None,
) -> None:
    roles = {r.lower() for r in (context.roles or [])}
    if roles & PROCUREMENT_READ_ROLES and action.endswith(".read"):
        return
    if roles & PROCUREMENT_ADMIN_ROLES:
        return
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        action=action,
        object_type=object_type,
        object_id=object_id or "procurement",
        object_context=context.object_context,
        company_id=company_id or context.company_id,
        amount=amount,
    )
    if not decision.allowed:
        raise PermissionError(decision.reason or "Procurement access denied")
