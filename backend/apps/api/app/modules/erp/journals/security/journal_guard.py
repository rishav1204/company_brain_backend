from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


def require_finance_journal_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms or "erp.journal.admin" in perms or "journal.admin" in perms:
        return context
    if "erp.gl.admin" in perms or "gl.admin" in perms:
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    raise HTTPException(status_code=403, detail="Finance admin required for journal operations")
