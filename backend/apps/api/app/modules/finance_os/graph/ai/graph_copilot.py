from __future__ import annotations

from app.modules.finance_os.graph.ai.graph_reasoner import build_context
from app.services import llm_provider


def answer(org_id: str, question: str, *, entity_id: str | None = None) -> dict:
    context = build_context(org_id, entity_id) if entity_id else ""
    if not context:
        try:
            from app.modules.finance_os.memory.ai.memory_reasoner import build_context as mem_ctx

            context = mem_ctx(org_id, question)
        except Exception:
            context = ""
    if not context:
        return {"answer": "No graph context found for this query.", "sources": []}
    if llm_provider.is_ready():
        try:
            result = llm_provider.generate_json(
                org_id=org_id,
                system_prompt="You are a finance graph copilot. Answer using graph relationships only.",
                user_prompt=f"Graph context:\n{context}\n\nQuestion: {question}",
                estimated_tokens=1200,
            )
            return {"answer": result.get("answer") or str(result), "sources": result.get("sources") or []}
        except Exception:
            pass
    return {"answer": context[:1000], "sources": []}
