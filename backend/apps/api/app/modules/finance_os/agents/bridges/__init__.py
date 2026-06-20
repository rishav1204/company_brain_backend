from __future__ import annotations

from app.modules.finance_os.agents.bridges import m27_bridge as _m27


def search(org_id: str, **kwargs) -> list[dict]:
    return _m27.search(org_id, **kwargs)
