from __future__ import annotations

from fastapi import HTTPException

READ_ROLES = {"finance_manager", "controller", "cfo", "auditor"}


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_graph_read(user: dict) -> None:
    enforce_billing(user.get("org_id"), "graph_engine")
    perms = set(user.get("permissions") or [])
    roles = set(user.get("roles") or [])
    if "graph.read" in perms or "finance_os.read" in perms:
        return
    if roles.intersection(READ_ROLES):
        return
    raise HTTPException(status_code=403, detail="graph.read permission required")


def require_graph_write(user: dict) -> None:
    enforce_billing(user.get("org_id"), "graph_engine")
    perms = set(user.get("permissions") or [])
    if "graph.write" in perms or "finance_admin" in perms or "finance_os.write" in perms:
        return
    raise HTTPException(status_code=403, detail="graph.write permission required")
