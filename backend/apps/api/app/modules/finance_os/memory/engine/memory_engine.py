from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository


def entity_context(org_id: str, *, entity_type: str, entity_id: str, top_k: int = 5) -> list[dict]:
    return entry_repository.list_active(org_id, entity_type=entity_type, entity_id=entity_id, limit=top_k)


def semantic_context(org_id: str, query: str, **kwargs) -> list[dict]:
    return search(org_id, query, **kwargs)
