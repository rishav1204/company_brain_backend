from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search


def build_context(org_id: str, query: str, *, memory_type: str | None = None, top_k: int = 8) -> str:
    hits = search(org_id, query, memory_type=memory_type, top_k=top_k)
    if not hits:
        return ""
    lines = []
    for hit in hits:
        lines.append(f"- [{hit.get('memory_type')}] {hit.get('title')}: {hit.get('content')}")
    return "\n".join(lines)
