from __future__ import annotations

from app.services.neo4j_service import neo4j_service


def search(org_id: str, *, query: str = "", label: str | None = None, top_k: int = 20) -> list[dict]:
    return neo4j_service.search_nodes(org_id, label=label, query_text=query, limit=top_k)
