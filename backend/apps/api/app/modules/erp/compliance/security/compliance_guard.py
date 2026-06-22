from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_compliance_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "compliance")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("compliance.admin", "compliance.modify", "tax.modify", "erp.tax.admin")):
        return context
    if any(r in roles for r in ("compliance_officer", "tax_manager", "cfo", "finance_admin")):
        return context
    raise HTTPException(status_code=403, detail="Compliance admin permission required")


def require_compliance_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "compliance")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("compliance.read", "compliance.modify", "tax.read", "tax.modify")):
        return context
    if any(r in roles for r in ("compliance_officer", "tax_manager", "cfo", "finance_admin", "finance_manager", "auditor")):
        return context
    return context
