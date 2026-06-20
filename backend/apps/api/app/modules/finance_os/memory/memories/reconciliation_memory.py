from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    if event_type == "reconciliation.completed":
        reason = payload.get("override_reason") or payload.get("match_notes")
        if not reason:
            return None
        return {
            "memory_type": "reconciliation",
            "entity_type": "bank_account",
            "entity_id": str(payload.get("bank_account_id")) if payload.get("bank_account_id") else None,
            "title": "Reconciliation override pattern",
            "content": f"Manual match note: {reason}",
            "importance_score": compute_importance(event_type=event_type),
            "references": [{"source_type": "reconciliation", "source_id": payload.get("reconciliation_id")}],
            "ttl_policy": "180d",
        }
    if event_type == "reconciliation.adjustment.posted":
        return {
            "memory_type": "reconciliation",
            "entity_type": "bank_account",
            "entity_id": str(payload.get("bank_account_id")) if payload.get("bank_account_id") else None,
            "title": "Reconciliation adjustment",
            "content": payload.get("reason") or "Adjustment posted during reconciliation",
            "importance_score": compute_importance(event_type=event_type),
            "references": [{"source_type": "reconciliation_adjustment", "source_id": payload.get("adjustment_id")}],
            "ttl_policy": "180d",
        }
    return None
