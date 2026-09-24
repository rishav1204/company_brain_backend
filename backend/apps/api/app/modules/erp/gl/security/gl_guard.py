from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_finance_gl_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "gl")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms or "erp.gl.admin" in perms or "gl.admin" in perms:
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    if "tenant_admin" in roles or "cfo" in roles or "controller" in roles:
        return context
    raise HTTPException(status_code=403, detail="Finance admin required for GL mutation")


def require_gl_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    """Read-only GL / trial balance / ledger listing."""
    enforce_billing(context.org_id, "gl")
    require_erp_read_access(
        context,
        permission_keys=[
            "journal.read",
            "erp.gl.read",
            "gl.read",
            "erp.gl.admin",
            "gl.admin",
            "fiscal.read",
        ],
        detail="GL read required",
    )
    return context

