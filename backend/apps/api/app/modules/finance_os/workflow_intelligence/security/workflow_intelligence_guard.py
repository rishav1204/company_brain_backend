from __future__ import annotations

from fastapi import HTTPException


def require_workflow_intelligence_read(user: dict) -> None:
    perms = set(user.get("permissions") or [])
    roles = {str(r).lower() for r in (user.get("roles") or [])}
    if "workflow_intelligence.read" in perms or "workflow.read" in perms:
        return
    if roles & {"finance_manager", "controller", "cfo", "finance_admin", "auditor"}:
        return
    raise HTTPException(status_code=403, detail="workflow_intelligence.read required")


def require_workflow_intelligence_write(user: dict) -> None:
    perms = set(user.get("permissions") or [])
    roles = {str(r).lower() for r in (user.get("roles") or [])}
    if "workflow_intelligence.write" in perms or "workflow.write" in perms:
        return
    if roles & {"finance_manager", "controller", "cfo", "finance_admin"}:
        return
    raise HTTPException(status_code=403, detail="workflow_intelligence.write required")
