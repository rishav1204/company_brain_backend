from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


def require_ap_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.ap.admin", "ap.admin", "invoice.approve", "payment.execute")):
        return context
    if any(r in roles for r in ("ap_manager", "ap_executive", "finance_admin")):
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    raise HTTPException(status_code=403, detail="AP admin permission required")


def require_ap_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.ap.admin", "ap.admin", "invoice.read", "invoice.create", "payment.read")):
        return context
    if any(r in roles for r in ("ap_manager", "ap_executive", "ap_preparer", "finance_admin")):
        return context
    return context
