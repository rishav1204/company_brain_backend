from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_treasury_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "treasury")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("payment.execute", "payment.approve", "bank.reconcile", "erp.treasury.admin")):
        return context
    if any(r in roles for r in ("treasury_manager", "cfo", "finance_admin")):
        return context
    raise HTTPException(status_code=403, detail="Treasury admin permission required")


def require_treasury_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "treasury")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("bank.read", "payment.execute", "erp.treasury.admin")):
        return context
    if any(r in roles for r in ("treasury_manager", "cfo", "finance_admin", "finance_manager")):
        return context
    return context
