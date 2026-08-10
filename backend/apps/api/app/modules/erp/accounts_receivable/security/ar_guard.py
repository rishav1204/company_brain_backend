from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_ar_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ar")
    require_erp_mutation_access(
        context,
        permission_keys=["erp.ar.admin", "ar.admin", "invoice.issue", "receipt.record", "ar.writeoff"],
        detail="AR admin permission required",
    )
    return context


def require_ar_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ar")
    require_erp_read_access(
        context,
        permission_keys=["erp.ar.admin", "ar.admin", "invoice.read", "receipt.read"],
        detail="AR read permission required",
    )
    return context
