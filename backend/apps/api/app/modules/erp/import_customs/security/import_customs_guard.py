from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_import_customs_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "procurement")
    require_erp_mutation_access(
        context,
        permission_keys=["erp.import_customs.admin", "erp.procurement.admin", "ap.admin"],
        detail="Import customs admin required",
    )
    return context


def require_import_customs_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "procurement")
    require_erp_read_access(
        context,
        permission_keys=["erp.import_customs.admin", "erp.import_customs.read", "erp.procurement.admin"],
        detail="Import customs read required",
    )
    return context
