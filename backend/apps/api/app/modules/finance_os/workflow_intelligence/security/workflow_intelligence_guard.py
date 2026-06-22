from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_workflow_intelligence_read(user: dict) -> None:
    enforce_billing(user.get("org_id"), "workflow_intelligence")
    perms = set(user.get("permissions") or [])
    roles = {str(r).lower() for r in (user.get("roles") or [])}
    if "workflow_intelligence.read" in perms or "workflow.read" in perms:
        return
    if roles & {"finance_manager", "controller", "cfo", "finance_admin", "auditor"}:
        return
    raise HTTPException(status_code=403, detail="workflow_intelligence.read required")


def require_workflow_intelligence_write(user: dict) -> None:
    enforce_billing(user.get("org_id"), "workflow_intelligence")
    perms = set(user.get("permissions") or [])
    roles = {str(r).lower() for r in (user.get("roles") or [])}
    if "workflow_intelligence.write" in perms or "workflow.write" in perms:
        return
    if roles & {"finance_manager", "controller", "cfo", "finance_admin"}:
        return
    raise HTTPException(status_code=403, detail="workflow_intelligence.write required")
