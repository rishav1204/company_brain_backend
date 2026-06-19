from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


def require_tax_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("gst.file", "tax.file", "tax.modify", "erp.tax.admin")):
        return context
    if any(r in roles for r in ("tax_manager", "compliance_officer", "cfo", "finance_admin")):
        return context
    raise HTTPException(status_code=403, detail="Tax admin permission required")


def require_tax_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("gst.read", "tax.read", "gst.file", "tax.file", "erp.tax.admin")):
        return context
    if any(r in roles for r in ("tax_manager", "compliance_officer", "cfo", "finance_admin", "finance_manager")):
        return context
    return context
