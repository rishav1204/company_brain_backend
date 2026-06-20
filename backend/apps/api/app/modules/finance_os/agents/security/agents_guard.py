from __future__ import annotations

from fastapi import HTTPException


def require_agent_read(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    if roles & {"tenant_admin", "finance_admin", "controller", "cfo", "auditor", "finance_os.read", "agent.read"}:
        return
    raise HTTPException(status_code=403, detail="Agent read access required")


def require_agent_run(user) -> None:
    roles = set(getattr(user, "roles", []) or [])
    if roles & {"tenant_admin", "finance_admin", "finance_os.write", "agent.run"}:
        return
    raise HTTPException(status_code=403, detail="Agent run access required")
