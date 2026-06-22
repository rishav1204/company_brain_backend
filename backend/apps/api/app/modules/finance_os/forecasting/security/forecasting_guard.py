from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_forecasting_read(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "forecasting")
    roles = set(getattr(user, "roles", []) or [])
    if roles & {"tenant_admin", "finance_admin", "controller", "cfo", "treasury_head", "auditor", "finance_os.read"}:
        return
    raise HTTPException(status_code=403, detail="Forecasting read access required")

