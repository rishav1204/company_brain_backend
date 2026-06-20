from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search


def search_memories(
    org_id: str,
    query: str,
    *,
    memory_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    return search(
        org_id,
        query,
        memory_type=memory_type,
        entity_type=entity_type,
        entity_id=entity_id,
        top_k=top_k,
    )
