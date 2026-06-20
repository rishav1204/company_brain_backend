from __future__ import annotations

from app.modules.finance_os.memory.engine.embedding_engine import embed_text
from app.modules.finance_os.memory.engine.ranking_engine import keyword_match, rank_candidates
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository
from app.modules.finance_os.memory.repositories.embedding_repository import embedding_repository
from app.services.repositories import memory_repo


def search(
    org_id: str,
    query: str,
    *,
    memory_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    top_k: int = 10,
    include_legacy: bool = True,
) -> list[dict]:
    candidates: list[dict] = []
    query_vec = embed_text(org_id, query)

    try:
        vector_hits = embedding_repository.search(
            org_id, query_embedding=query_vec, top_k=top_k * 2, memory_type=memory_type
        )
        for hit in vector_hits:
            if entity_type and hit.get("entity_type") != entity_type:
                continue
            if entity_id and hit.get("entity_id") != entity_id:
                continue
            et = hit.get("entity_type")
            eid = hit.get("entity_id")
            count = 1
            if et and eid:
                count = entry_repository.count_by_entity(
                    org_id, entity_type=et, entity_id=eid, memory_type=hit.get("memory_type", "")
                )
            candidates.append({**hit, "entity_memory_count": count, "source": "vector"})
    except Exception:
        pass

    if entity_type and entity_id:
        try:
            rows = entry_repository.list_active(
                org_id, memory_type=memory_type, entity_type=entity_type, entity_id=entity_id, limit=top_k * 2
            )
            for row in rows:
                candidates.append({**row, "distance": 0.3, "entity_memory_count": len(rows), "source": "entity"})
        except Exception:
            pass
    elif not candidates:
        try:
            rows = entry_repository.list_active(org_id, memory_type=memory_type, limit=top_k * 2)
            for row in rows:
                kw = keyword_match(query, str(row.get("content", "")))
                if kw > 0 or not query.strip():
                    candidates.append({**row, "distance": 1.0 - kw, "entity_memory_count": 1, "source": "keyword"})
        except Exception:
            pass

    if include_legacy:
        subject_ref = f"{entity_type}:{entity_id}" if entity_type and entity_id else None
        try:
            for row in memory_repo.list_memory(org_id=org_id, subject_ref=subject_ref, memory_type=memory_type):
                payload = row.get("payload_jsonb") or {}
                if payload.get("status") in {"expired", "archived"}:
                    continue
                content = payload.get("content") or str(payload)
                candidates.append(
                    {
                        "id": row["id"],
                        "memory_type": row.get("memory_type"),
                        "title": payload.get("title", "Legacy memory"),
                        "content": content,
                        "importance_score": float(row.get("relevance_score", 0.5)) * 100,
                        "distance": 0.5,
                        "entity_memory_count": 1,
                        "source": "legacy",
                    }
                )
        except Exception:
            pass

    deduped: dict[str, dict] = {}
    for c in candidates:
        key = str(c.get("id", c.get("content", ""))[:80])
        if key not in deduped or c.get("final_score", 0) > deduped[key].get("final_score", 0):
            deduped[key] = c
    return rank_candidates(list(deduped.values()), query=query)[:top_k]
