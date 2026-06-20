from __future__ import annotations

from app.modules.finance_os.graph.engine.causality_engine import explain_chain
from app.modules.finance_os.graph.events.graph_events import emit_root_cause_generated


def root_cause(org_id: str, entity_id: str, *, trace_id: str | None = None) -> dict:
    result = explain_chain(org_id, entity_id)
    if result.get("confidence", 0) >= 0.7:
        emit_root_cause_generated(org_id, result, trace_id=trace_id)
    return result
