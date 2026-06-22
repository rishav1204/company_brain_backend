from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_analytics_read(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "analytics")
    roles = set(getattr(user, "roles", []) or [])
    allowed = {
        "tenant_admin",
        "finance_manager",
        "controller",
        "cfo",
        "ceo",
        "auditor",
        "board_viewer",
        "finance_admin",
        "finance_os.read",
    }
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Analytics read access required")


def require_analytics_refresh(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "analytics")
    roles = set(getattr(user, "roles", []) or [])
    allowed = {"tenant_admin", "finance_manager", "controller", "cfo", "finance_admin"}
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Analytics refresh access required")
