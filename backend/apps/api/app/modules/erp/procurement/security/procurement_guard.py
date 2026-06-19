from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import RequestContext, build_request_context


PROCUREMENT_ADMIN_ROLES = {
    "procurement_manager", "buyer", "cfo", "controller", "finance_manager", "tenant_admin", "ap_manager",
}
PROCUREMENT_READ_ROLES = PROCUREMENT_ADMIN_ROLES | {"requester", "auditor", "analyst"}


def _check(context: RequestContext, *, read_only: bool = False) -> RequestContext:
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "procurement.admin" in perms:
        return context
    if read_only and roles & PROCUREMENT_READ_ROLES:
        return context
    if not read_only and roles & PROCUREMENT_ADMIN_ROLES:
        return context
    if read_only and any(p.startswith("procurement.") for p in perms):
        return context
    if not read_only and any(p in perms for p in ("procurement.create", "procurement.approve", "procurement.receive")):
        return context
    raise HTTPException(status_code=403, detail="Procurement access required")


def require_procurement_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, read_only=True)


def require_procurement_create(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_procurement_approve(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_procurement_receive(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_procurement_match(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_procurement_override(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = {r.lower() for r in (context.roles or [])}
    if roles & {"cfo", "controller", "finance_manager", "tenant_admin"}:
        return context
    return _check(context)

