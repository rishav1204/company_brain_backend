from __future__ import annotations

from app.modules.finance_os.audit_explorer.engine.timeline_engine import build_timeline


def get_timeline(org_id: str, *, object_type: str, object_id: str, limit: int = 200) -> list[dict]:
    return build_timeline(org_id, object_type=object_type, object_id=object_id, limit=limit)
