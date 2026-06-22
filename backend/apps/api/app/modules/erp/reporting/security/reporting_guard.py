from __future__ import annotations

from fastapi import HTTPException


def require_reporting_read(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    allowed = {
        "tenant_admin",
        "accountant",
        "finance_manager",
        "controller",
        "cfo",
        "auditor",
        "finance_admin",
        "finance_os.read",
    }
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Reporting read access required")


def require_reporting_export(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    allowed = {"tenant_admin", "finance_manager", "controller", "cfo", "finance_admin"}
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Reporting export access required")
