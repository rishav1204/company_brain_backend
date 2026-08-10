from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_ap_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ap")
    require_erp_mutation_access(
        context,
        permission_keys=["erp.ap.admin", "ap.admin", "invoice.approve", "payment.execute"],
        detail="AP admin permission required",
    )
    return context


def require_ap_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "ap")
    require_erp_read_access(
        context,
        permission_keys=["erp.ap.admin", "ap.admin", "invoice.read", "invoice.create", "payment.read"],
        detail="AP read permission required",
    )
    return context
