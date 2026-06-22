from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_voucher_admin(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "vouchers")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.voucher.admin", "voucher.admin", "erp.journal.admin", "journal.admin")):
        return context
    if any(r in roles for r in ("finance_admin", "accountant", "ap_manager", "ar_manager")):
        return context
    if any("finance" in r and "admin" in r for r in roles):
        return context
    raise HTTPException(status_code=403, detail="Voucher admin permission required")


def require_voucher_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "vouchers")
    roles = [r.lower() for r in (context.roles or [])]
    perms = [p.lower() for p in (context.permissions or [])]
    if "*" in perms:
        return context
    if any(p in perms for p in ("erp.voucher.admin", "voucher.read", "erp.journal.admin", "journal.read")):
        return context
    if any(r in roles for r in ("finance_admin", "accountant", "ap_manager", "ar_manager", "ap_executive", "ap_preparer")):
        return context
    raise HTTPException(status_code=403, detail="Voucher read permission required")
