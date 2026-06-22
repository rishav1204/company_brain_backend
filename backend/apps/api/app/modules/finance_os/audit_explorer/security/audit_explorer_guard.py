from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_audit_read(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "audit_explorer")
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
    enforce_billing(getattr(user, "org_id", None), "audit_explorer")
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
    enforce_billing(getattr(user, "org_id", None), "audit_explorer")
    roles = set(getattr(user, "roles", []) or [])
    allowed = {"tenant_admin", "finance_manager", "controller", "cfo", "finance_admin", "governance_admin", "admin"}
    if roles & allowed:
        return
    raise HTTPException(status_code=403, detail="Audit refresh access required")
