from __future__ import annotations


def compliance_context(org_id: str, entity_id: str | None) -> dict:
    try:
        from app.modules.finance_os.memory.engine.retrieval_engine import search

        hits = search(org_id, "GST compliance", memory_type="compliance", top_k=3)
        return {"entity_id": entity_id, "compliance_memories": len(hits)}
    except Exception:
        return {"entity_id": entity_id}
