from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_agent_read(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "agents")
    roles = set(getattr(user, "roles", []) or [])
    if roles & {"tenant_admin", "finance_admin", "controller", "cfo", "auditor", "finance_os.read", "agent.read"}:
        return
    raise HTTPException(status_code=403, detail="Agent read access required")


def require_agent_run(user) -> None:
    enforce_billing(getattr(user, "org_id", None), "agents")
    roles = set(getattr(user, "roles", []) or [])
    if roles & {"tenant_admin", "finance_admin", "finance_os.write", "agent.run"}:
        return
    raise HTTPException(status_code=403, detail="Agent run access required")
