from __future__ import annotations

from fastapi import HTTPException


def require_analytics_read(user) -> None:
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
    roles = set(getattr(user, "roles", []) or [])
    allowed = {"tenant_admin", "finance_manager", "controller", "cfo", "finance_admin"}
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Analytics refresh access required")
