from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search as memory_search


def search_memories(
    org_id: str,
    query: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    top_k: int = 8,
) -> list[dict]:
    try:
        return memory_search(org_id, query, entity_type=entity_type, entity_id=entity_id, top_k=top_k)
    except Exception:
        return []


def search(
    org_id: str,
    query: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    top_k: int = 8,
) -> list[dict]:
    return search_memories(org_id, query, entity_type=entity_type, entity_id=entity_id, top_k=top_k)
