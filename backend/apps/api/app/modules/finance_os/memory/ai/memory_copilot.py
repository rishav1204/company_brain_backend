from __future__ import annotations

from app.modules.finance_os.memory.ai.memory_reasoner import build_context
from app.services import llm_provider


def answer(org_id: str, question: str, *, memory_type: str | None = None) -> dict:
    context = build_context(org_id, question, memory_type=memory_type)
    if not context:
        return {"answer": "No relevant organizational memories found.", "sources": []}
    if llm_provider.is_ready():
        try:
            result = llm_provider.generate_json(
                org_id=org_id,
                system_prompt="You are a finance memory copilot. Answer using only provided memories.",
                user_prompt=f"Memories:\n{context}\n\nQuestion: {question}",
                estimated_tokens=1200,
            )
            return {
                "answer": result.get("answer") or result.get("summary") or str(result),
                "sources": result.get("sources") or [],
            }
        except Exception:
            pass
    return {"answer": f"Based on memories: {context[:800]}", "sources": []}
