from __future__ import annotations

from app.modules.finance_os.audit_explorer.engine.timeline_engine import correlate_by_trace


def trace_related_events(org_id: str, trace_id: str | None) -> list[dict]:
    if not trace_id:
        return []
    return correlate_by_trace(org_id, trace_id)
