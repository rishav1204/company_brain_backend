from __future__ import annotations

from app.modules.finance_os.graph.engine.dependency_engine import get_dependents
from app.modules.finance_os.graph.events.graph_events import emit_dependency_detected


def dependencies(org_id: str, entity_id: str, *, max_depth: int = 4, trace_id: str | None = None) -> dict:
    result = get_dependents(org_id, entity_id, max_depth=max_depth)
    if result.get("count", 0) > 0:
        emit_dependency_detected(org_id, {"entity_id": entity_id, "count": result["count"]}, trace_id=trace_id)
    return result
