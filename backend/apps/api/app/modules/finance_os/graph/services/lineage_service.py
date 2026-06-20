from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import get_lifecycle
from app.modules.finance_os.graph.events.graph_events import emit_lineage_generated


def lineage(org_id: str, entity_id: str, *, direction: str = "both", max_depth: int = 6, trace_id: str | None = None) -> dict:
    result = get_lifecycle(org_id, entity_id, direction=direction, max_depth=max_depth)
    emit_lineage_generated(org_id, {"entity_id": entity_id, "count": result.get("count")}, trace_id=trace_id)
    return result
