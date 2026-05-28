from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext

_WRITE_ROLES = frozenset({"admin", "governance_admin", "finance_admin"})
_AUDITOR_ROLES = frozenset({"auditor", "governance_admin", "admin"})


def require_auditor_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    if not any(role in _AUDITOR_ROLES for role in context.roles):
        raise HTTPException(status_code=403, detail="auditor or admin role required for audit read access")
    return context


def require_governance_write(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    if any(role == "auditor" for role in context.roles) and not any(
        role in _WRITE_ROLES for role in context.roles
    ):
        raise HTTPException(status_code=403, detail="auditor role is read-only for governance mutations")
    return context


def require_governance_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    if not any(role in {"governance_admin", "admin"} for role in context.roles):
        raise HTTPException(status_code=403, detail="governance_admin role required")
    return context
