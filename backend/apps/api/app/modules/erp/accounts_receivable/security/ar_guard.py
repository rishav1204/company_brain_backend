from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_ar_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ar")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.ar.admin", "ar.admin", "invoice.issue", "receipt.record", "ar.writeoff")):
        return context
    if any(r in roles for r in ("ar_manager", "ar_executive", "finance_admin", "sales_admin")):
        return context
    raise HTTPException(status_code=403, detail="AR admin permission required")


def require_ar_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ar")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.ar.admin", "ar.admin", "invoice.read", "receipt.read")):
        return context
    if any(r in roles for r in ("ar_manager", "ar_executive", "ar_clerk", "finance_admin", "sales_admin")):
        return context
    return context
