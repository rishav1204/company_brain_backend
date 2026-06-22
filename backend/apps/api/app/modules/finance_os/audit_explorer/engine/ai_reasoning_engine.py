from __future__ import annotations

from app.modules.finance_os.audit_explorer.repositories.ai_decision_repository import ai_decision_repository
from app.modules.finance_os.audit_explorer.read_models import agent_read_models, audit_read_models, graph_memory_read_models


def explain_execution(org_id: str, execution_id: str) -> dict:
    trails = ai_decision_repository.get_by_execution(org_id, execution_id)
    execution = agent_read_models.get_execution(org_id, execution_id)
    recommendations = agent_read_models.list_recommendations(org_id, execution_id)
    entity_type = (execution or {}).get("entity_type") or "agent_execution"
    entity_id = (execution or {}).get("entity_id") or execution_id
    memory_factors = graph_memory_read_models.search_entity_memories(
        org_id, entity_type=str(entity_type), entity_id=str(entity_id)
    )
    enriched = []
    for trail in trails:
        trace_id = trail.get("ai_trace_id")
        if trace_id:
            trace = audit_read_models.get_ai_trace(org_id, str(trace_id))
            if trace:
                trail = {**trail, "governance_trace": trace}
        enriched.append(trail)
    if not enriched and recommendations:
        for rec in recommendations:
            enriched.append(
                {
                    "decision_type": rec.get("recommendation_type"),
                    "reasoning_summary": rec.get("recommendation"),
                    "confidence_score": rec.get("confidence_score"),
                    "outcome": rec.get("status"),
                    "recommendation_id": rec.get("id"),
                }
            )
    return {
        "trails": enriched,
        "execution": execution,
        "recommendations": recommendations,
        "memory_factors": memory_factors,
    }
