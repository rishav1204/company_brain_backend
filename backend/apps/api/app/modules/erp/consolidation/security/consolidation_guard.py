from __future__ import annotations

from fastapi import HTTPException

from app.modules.core.iam.services.access_control import evaluate_access
from app.services.object_context import ObjectContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_consolidation_read(context) -> None:
    enforce_billing(context.org_id, "consolidation")
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action="consolidation.read",
        object_context=ObjectContext(object_type="consolidation", object_id=""),
        attrs=context.attrs or {},
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason or "consolidation_read_denied")


def require_consolidation_run(context, *, company_id: str | None = None) -> None:
    enforce_billing(context.org_id, "consolidation")
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action="consolidation.run",
        object_context=ObjectContext(object_type="consolidation", object_id="", company_id=company_id),
        attrs=context.attrs or {},
        object_company_id=company_id,
    )
    if not decision.allowed:
        role_set = {r.lower() for r in (context.roles or [])}
        if not role_set & {"tenant_admin", "cfo", "controller", "finance_admin"}:
            raise HTTPException(status_code=403, detail=decision.reason or "consolidation_run_denied")


def require_intercompany_write(context, *, company_id: str | None = None) -> None:
    enforce_billing(context.org_id, "consolidation")
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action="intercompany.create",
        object_context=ObjectContext(object_type="intercompany", object_id="", company_id=company_id),
        attrs=context.attrs or {},
        object_company_id=company_id,
    )
    if not decision.allowed:
        role_set = {r.lower() for r in (context.roles or [])}
        if not role_set & {"tenant_admin", "cfo", "controller", "finance_manager"}:
            raise HTTPException(status_code=403, detail=decision.reason or "intercompany_denied")
