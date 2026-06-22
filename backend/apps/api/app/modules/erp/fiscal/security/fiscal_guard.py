from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_fiscal_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "gl")
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "fiscal.read" in perms or "erp.fiscal.admin" in perms:
        return context
    if roles & {"cfo", "controller", "finance_manager", "auditor", "analyst", "tenant_admin"}:
        return context
    raise HTTPException(status_code=403, detail="Fiscal read access required")


def require_fiscal_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "gl")
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "fiscal.close" in perms or "erp.fiscal.admin" in perms:
        return context
    if roles & {"cfo", "controller", "tenant_admin"}:
        return context
    raise HTTPException(status_code=403, detail="Fiscal admin access required")
