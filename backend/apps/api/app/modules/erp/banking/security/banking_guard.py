from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_banking_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "banking")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("bank.modify", "treasury.modify", "erp.banking.admin")):
        return context
    if any(r in roles for r in ("finance_manager", "finance_executive", "treasury_executive", "treasury_manager", "cfo", "controller", "finance_admin")):
        return context
    raise HTTPException(status_code=403, detail="Banking admin permission required")


def require_banking_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "banking")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("bank.read", "bank.reconcile", "treasury.read", "treasury.modify")):
        return context
    if any(r in roles for r in ("finance_manager", "finance_executive", "treasury_executive", "treasury_manager", "cfo", "controller", "finance_admin", "auditor")):
        return context
    return context
