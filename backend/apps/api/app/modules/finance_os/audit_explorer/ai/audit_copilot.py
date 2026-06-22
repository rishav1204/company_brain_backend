from __future__ import annotations

from app.modules.finance_os.audit_explorer.ai.audit_reasoner import build_context
from app.modules.finance_os.audit_explorer.ai.explanation_generator import generate_explanation
from app.services.llm_provider import llm_provider


def answer(org_id: str, question: str, *, object_type: str | None = None, object_id: str | None = None) -> dict:
    explanation = generate_explanation(org_id, question, object_type=object_type, object_id=object_id)
    context = explanation.get("context") or build_context(org_id, question, object_type=object_type, object_id=object_id)
    if not llm_provider.is_ready():
        return {
            "answer": f"Audit context:\n{context[:1500]}",
            "sources": explanation.get("sources") or {},
            "confidence_band": "review",
        }
    try:
        out = llm_provider.generate_json(
            org_id=org_id,
            system_prompt=(
                "You are an enterprise audit copilot for CFOs, auditors, and compliance officers. "
                "Answer who did what, when, why, and what evidence exists. Never invent chain-of-thought. "
                "Output strict JSON only."
            ),
            user_prompt=(
                f"{context}\n\nAnswer the audit question with citations to timeline events and evidence.\n"
                "Return JSON: {answer: str, sources: {}, confidence_band: str}"
            ),
            estimated_tokens=1800,
        )
        return {
            "answer": str(out.get("answer") or ""),
            "sources": out.get("sources") or explanation.get("sources") or {},
            "confidence_band": str(out.get("confidence_band") or "review"),
        }
    except Exception:
        return {"answer": context[:1500], "sources": explanation.get("sources") or {}, "confidence_band": "manual"}
