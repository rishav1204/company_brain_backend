from __future__ import annotations

from app.modules.finance_os.analytics.ai.executive_reasoner import build_context
from app.services.llm_provider import llm_provider


def answer(org_id: str, question: str) -> dict:
    context = build_context(org_id, question)
    if not llm_provider.is_ready():
        return {"answer": f"Based on latest KPIs and insights:\n{context[:1200]}", "sources": {}, "confidence_band": "review"}
    try:
        out = llm_provider.generate_json(
            org_id=org_id,
            system_prompt="You are an executive financial copilot for CFOs and board members. Output strict JSON only. Read-only analysis.",
            user_prompt=(
                f"{context}\n\nAnswer the executive question concisely with causes and recommended focus areas.\n"
                "Return JSON: {answer: str, sources: {}, confidence_band: str}"
            ),
            estimated_tokens=1600,
        )
        return {
            "answer": str(out.get("answer") or ""),
            "sources": out.get("sources") or {},
            "confidence_band": str(out.get("confidence_band") or "review"),
        }
    except Exception:
        return {"answer": context[:1200], "sources": {}, "confidence_band": "manual"}
