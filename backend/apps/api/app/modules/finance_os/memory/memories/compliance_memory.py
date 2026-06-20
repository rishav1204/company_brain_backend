from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    if event_type in {"compliance.alert.generated", "compliance.alert", "gst.mismatch.detected"}:
        return {
            "memory_type": "compliance",
            "entity_type": "compliance",
            "entity_id": None,
            "title": payload.get("alert_type") or "Compliance alert",
            "content": payload.get("message") or payload.get("detail") or event_type,
            "importance_score": compute_importance(event_type=event_type, compliance=True),
            "references": [{"source_type": "compliance", "source_id": payload.get("alert_id")}],
            "ttl_policy": "forever",
        }
    return None
