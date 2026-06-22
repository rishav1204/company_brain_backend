from __future__ import annotations

from app.modules.finance_os.audit_explorer.ai.audit_reasoner import build_context, gather_sources


def generate_explanation(org_id: str, question: str, *, object_type: str | None = None, object_id: str | None = None) -> dict:
    context = build_context(org_id, question, object_type=object_type, object_id=object_id)
    sources = gather_sources(org_id, object_type=object_type, object_id=object_id)
    return {
        "context": context,
        "sources": sources,
        "summary": context[:800],
    }
