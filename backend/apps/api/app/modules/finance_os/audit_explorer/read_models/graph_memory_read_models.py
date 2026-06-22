from __future__ import annotations

from app.modules.finance_os.graph.services.lineage_service import lineage
from app.modules.finance_os.memory.services.retrieval_service import search_memories


def get_lineage(org_id: str, entity_id: str, *, trace_id: str | None = None) -> dict:
    return lineage(org_id, entity_id, trace_id=trace_id)


def search_entity_memories(org_id: str, *, entity_type: str, entity_id: str, query: str = "") -> list[dict]:
    q = query or f"{entity_type} {entity_id}"
    return search_memories(org_id, q, entity_type=entity_type, entity_id=entity_id, top_k=10)
