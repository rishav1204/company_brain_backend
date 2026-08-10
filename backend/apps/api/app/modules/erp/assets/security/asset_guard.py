from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def _mutation(context: RequestContext, *, keys: list[str], detail: str) -> RequestContext:
    enforce_billing(context.org_id, "assets")
    require_erp_mutation_access(context, permission_keys=keys, detail=detail)
    return context


def require_asset_create(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.create', 'erp.assets.admin', 'assets.admin'], detail="Asset create required")


def require_asset_capitalize(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.capitalize', 'erp.assets.admin', 'assets.admin'], detail="Asset capitalize required")


def require_asset_depreciate(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.depreciate', 'erp.assets.admin'], detail="Asset depreciate required")


def require_asset_transfer(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.transfer', 'erp.assets.admin'], detail="Asset transfer required")


def require_asset_impair(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.impair', 'erp.assets.admin'], detail="Asset impair required")


def require_asset_dispose(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _mutation(context, keys=['erp.assets.dispose', 'erp.assets.admin'], detail="Asset dispose required")


def require_asset_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "assets")
    require_erp_read_access(
        context,
        permission_keys=['erp.assets.admin', 'assets.read', 'assets.admin'],
        detail="Asset read required",
    )
    return context
