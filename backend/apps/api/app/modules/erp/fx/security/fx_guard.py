from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_fx_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "gl")
    require_erp_mutation_access(
        context,
        permission_keys=["erp.fx.admin", "erp.gl.admin", "gl.admin"],
        detail="FX admin required",
    )
    return context


def require_fx_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "gl")
    require_erp_read_access(
        context,
        permission_keys=["erp.fx.admin", "erp.fx.read", "erp.gl.admin", "gl.read"],
        detail="FX read required",
    )
    return context
