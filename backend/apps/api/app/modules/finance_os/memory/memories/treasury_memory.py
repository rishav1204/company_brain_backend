from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    if event_type == "liquidity_alert.created":
        return {
            "memory_type": "treasury",
            "entity_type": "org",
            "entity_id": None,
            "title": "Liquidity stress event",
            "content": payload.get("message") or "Liquidity alert triggered",
            "importance_score": compute_importance(event_type=event_type, amount=_amount(payload)),
            "references": [{"source_type": "liquidity_alert", "source_id": payload.get("alert_id")}],
            "ttl_policy": "forever",
        }
    if event_type in {"cash.forecast.updated", "treasury.risk.detected"}:
        return {
            "memory_type": "treasury",
            "entity_type": "org",
            "entity_id": None,
            "title": "Treasury signal",
            "content": payload.get("summary") or str(event_type),
            "importance_score": compute_importance(event_type=event_type),
            "references": [{"source_type": "treasury", "source_id": payload.get("forecast_id")}],
            "ttl_policy": "180d",
        }
    return None


def _amount(payload: dict) -> float | None:
    raw = payload.get("amount") or payload.get("shortfall")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
