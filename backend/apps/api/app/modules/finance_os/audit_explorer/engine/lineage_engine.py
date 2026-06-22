from __future__ import annotations

from app.modules.finance_os.audit_explorer.read_models import graph_memory_read_models


def get_entity_lineage(org_id: str, entity_id: str, *, trace_id: str | None = None) -> dict:
    try:
        return graph_memory_read_models.get_lineage(org_id, entity_id, trace_id=trace_id)
    except Exception:
        return {"entity_id": entity_id, "nodes": [], "edges": [], "count": 0}
