from __future__ import annotations

from app.modules.finance_os.audit_explorer.services.audit_explorer_service import explore
from app.modules.finance_os.audit_explorer.services.timeline_service import get_timeline
from app.modules.finance_os.audit_explorer.services.audit_evidence_service import get_evidence
from app.modules.finance_os.audit_explorer.services.ai_explanation_service import get_ai_decision
from app.modules.finance_os.audit_explorer.services.workflow_trace_service import get_approval_chain
from app.modules.finance_os.audit_explorer.services.audit_search_service import search
from app.modules.finance_os.audit_explorer.engine.lineage_engine import get_entity_lineage


def build_context(org_id: str, question: str, *, object_type: str | None = None, object_id: str | None = None) -> str:
    parts = [f"Question: {question}"]
    if object_type and object_id:
        view = explore(org_id, object_type=object_type, object_id=object_id)
        parts.append(f"Timeline events: {len(view.get('timeline', []))}")
        parts.append(f"Evidence items: {len(view.get('evidence', []))}")
        parts.append(f"AI decisions: {len(view.get('ai_decisions', []))}")
        for entry in (view.get("timeline") or [])[-5:]:
            parts.append(f"- {entry.get('event_type')} @ {entry.get('event_timestamp')}")
    else:
        hits = search(org_id, q=question, limit=5)
        for hit in hits:
            parts.append(f"- {hit.get('event_type')} on {hit.get('object_type')}:{hit.get('object_id')}")
    return "\n".join(parts)


def gather_sources(org_id: str, *, object_type: str | None, object_id: str | None) -> dict:
    sources: dict = {}
    if object_type and object_id:
        sources["timeline"] = get_timeline(org_id, object_type=object_type, object_id=object_id)
        sources["evidence"] = get_evidence(org_id, object_type=object_type, object_id=object_id)
        sources["lineage"] = get_entity_lineage(org_id, object_id)
    return sources
