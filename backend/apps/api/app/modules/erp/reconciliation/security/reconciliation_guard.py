from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


def require_reconciliation_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("reconciliation.modify", "bank.reconcile", "treasury.modify", "erp.reconciliation.admin")):
        return context
    if any(r in roles for r in ("finance_manager", "finance_executive", "controller", "cfo", "treasury_executive")):
        return context
    raise HTTPException(status_code=403, detail="Reconciliation admin permission required")


def require_reconciliation_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("reconciliation.read", "bank.reconcile", "bank.read", "treasury.read")):
        return context
    if any(r in roles for r in ("finance_manager", "finance_executive", "controller", "cfo", "auditor", "treasury_executive")):
        return context
    raise HTTPException(status_code=403, detail="Reconciliation read permission required")
