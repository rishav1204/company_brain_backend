from __future__ import annotations


def predict_demand(*, item_id: str, horizon_days: int = 30) -> dict:
    return {
        "item_id": item_id,
        "horizon_days": horizon_days,
        "predicted_quantity": None,
        "confidence": 0.0,
        "model": "stub",
    }
