from __future__ import annotations

from app.modules.finance_os.audit_explorer.engine.timeline_engine import build_timeline
from app.modules.finance_os.audit_explorer.engine.evidence_engine import collect_evidence
from app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine import explain_execution
from app.modules.finance_os.audit_explorer.engine.lineage_engine import get_entity_lineage
from app.modules.finance_os.audit_explorer.repositories.ai_decision_repository import ai_decision_repository


def explore(org_id: str, *, object_type: str, object_id: str, trace_id: str | None = None) -> dict:
    timeline = build_timeline(org_id, object_type=object_type, object_id=object_id)
    evidence = collect_evidence(org_id, object_type=object_type, object_id=object_id)
    ai_decisions: list[dict] = []
    if object_type == "agent_execution":
        ai_decisions = explain_execution(org_id, object_id).get("trails", [])
    else:
        for entry in timeline:
            meta = entry.get("metadata") or {}
            exec_id = meta.get("execution_id") or meta.get("agent_execution_id")
            if exec_id:
                ai_decisions.extend(ai_decision_repository.get_by_execution(org_id, str(exec_id)))
    lineage = get_entity_lineage(org_id, object_id, trace_id=trace_id)
    return {
        "object_type": object_type,
        "object_id": object_id,
        "timeline": timeline,
        "evidence": evidence.get("materialized", []) + evidence.get("governance", []),
        "ai_decisions": ai_decisions,
        "lineage": lineage,
    }
