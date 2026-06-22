from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import RequestContext, build_request_context


ASSET_ADMIN_ROLES = {
    "asset_manager", "finance_controller", "cfo", "controller", "finance_manager", "tenant_admin",
}
ASSET_READ_ROLES = ASSET_ADMIN_ROLES | {"auditor", "analyst"}


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def _check(context: RequestContext, *, read_only: bool = False, action: str | None = None) -> RequestContext:
    enforce_billing(context.org_id, "assets")
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "asset.admin" in perms:
        return context
    if action and f"asset.{action}" in perms:
        return context
    if read_only and roles & ASSET_READ_ROLES:
        return context
    if not read_only and roles & ASSET_ADMIN_ROLES:
        return context
    if read_only and any(p.startswith("asset.") for p in perms):
        return context
    if not read_only and any(p in perms for p in ("asset.create", "asset.capitalize")):
        return context
    raise HTTPException(status_code=403, detail="Asset access required")


def require_asset_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, read_only=True)


def require_asset_create(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_asset_capitalize(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="capitalize")


def require_asset_depreciate(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="depreciate")


def require_asset_transfer(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="transfer")


def require_asset_dispose(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="dispose")


def require_asset_impair(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, action="impair")
