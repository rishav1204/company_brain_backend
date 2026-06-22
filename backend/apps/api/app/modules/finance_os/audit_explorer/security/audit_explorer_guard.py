from __future__ import annotations

from fastapi import HTTPException


def require_audit_read(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    allowed = {
        "tenant_admin",
        "finance_manager",
        "controller",
        "cfo",
        "auditor",
        "compliance_officer",
        "governance_admin",
        "admin",
        "finance_admin",
        "finance_os.read",
    }
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Audit explorer read access required")


def require_audit_copilot(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    allowed = {
        "tenant_admin",
        "finance_manager",
        "controller",
        "cfo",
        "auditor",
        "compliance_officer",
        "governance_admin",
        "admin",
        "finance_admin",
    }
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Audit copilot access required")


def require_audit_refresh(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    allowed = {"tenant_admin", "finance_manager", "controller", "cfo", "finance_admin", "governance_admin", "admin"}
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Audit refresh access required")
