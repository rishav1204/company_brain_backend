from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_finance_journal_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "journals")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms or "erp.journal.admin" in perms or "journal.admin" in perms:
        return context
    if "erp.gl.admin" in perms or "gl.admin" in perms:
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    if "tenant_admin" in roles or "cfo" in roles or "controller" in roles:
        return context
    raise HTTPException(status_code=403, detail="Finance admin required for journal operations")


def require_journal_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    """Read-only journal list / approval queue."""
    enforce_billing(context.org_id, "journals")
    roles = [r.lower() for r in (context.roles or [])]
    if "tenant_admin" in roles or "cfo" in roles or "controller" in roles:
        return context
    require_erp_read_access(
        context,
        permission_keys=[
            "journal.read",
            "erp.journal.read",
            "erp.journal.admin",
            "journal.admin",
            "erp.gl.read",
            "gl.read",
        ],
        detail="Journal read required",
    )
    return context
