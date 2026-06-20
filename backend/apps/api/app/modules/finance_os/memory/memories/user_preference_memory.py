from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    if event_type == "decision.recorded":
        return {
            "memory_type": "user",
            "entity_type": "decision",
            "entity_id": str(payload.get("decision_id")) if payload.get("decision_id") else None,
            "title": payload.get("title") or "Recorded decision",
            "content": payload.get("rationale") or payload.get("summary") or "Finance decision recorded",
            "importance_score": compute_importance(event_type=event_type),
            "references": [{"source_type": "decision", "source_id": payload.get("decision_id")}],
            "ttl_policy": "forever",
        }
    user_id = payload.get("user_id") or payload.get("assignee_id")
    preference = payload.get("preference") or payload.get("user_preference")
    if user_id and preference:
        return {
            "memory_type": "user",
            "entity_type": "user",
            "entity_id": str(user_id),
            "title": "User preference",
            "content": str(preference),
            "importance_score": 55.0,
            "references": [{"source_type": "user", "source_id": user_id}],
            "ttl_policy": "180d",
        }
    return None
