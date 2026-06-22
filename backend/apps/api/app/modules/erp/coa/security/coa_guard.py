from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_finance_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "coa")
    """
    Minimal guard: require role containing 'finance' and 'admin', or wildcard permission.
    Extend to exact IAM permission mapping later.
    """
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms or "erp.coa.admin" in perms or "coa.admin" in perms:
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    raise HTTPException(status_code=403, detail="Finance admin required for COA mutation")

