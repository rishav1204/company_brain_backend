from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import RequestContext, build_request_context


INVENTORY_ADMIN_ROLES = {
    "warehouse_manager", "inventory_controller", "finance_controller", "cfo",
    "controller", "finance_manager", "tenant_admin",
}
INVENTORY_READ_ROLES = INVENTORY_ADMIN_ROLES | {"auditor", "analyst"}


def _check(context: RequestContext, *, read_only: bool = False, action: str | None = None) -> RequestContext:
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "inventory.admin" in perms:
        return context
    if action and f"inventory.{action}" in perms:
        return context
    if read_only and roles & INVENTORY_READ_ROLES:
        return context
    if not read_only and roles & INVENTORY_ADMIN_ROLES:
        return context
    if read_only and any(p.startswith("inventory.") for p in perms):
        return context
    if not read_only and any(p in perms for p in ("inventory.create", "inventory.receive", "inventory.issue")):
        return context
    raise HTTPException(status_code=403, detail="Inventory access required")


def require_inventory_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, read_only=True)


def require_inventory_create(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="create")


def require_inventory_receive(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="receive")


def require_inventory_issue(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="issue")


def require_inventory_transfer(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="transfer")


def require_inventory_adjust(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="adjust")


def require_inventory_value(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="value")
