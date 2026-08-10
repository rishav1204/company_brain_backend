from __future__ import annotations

from statistics import mean

from app.modules.erp.query_services import intel_reads


def predict_demand(org_id: str, *, item_id: str, horizon_days: int = 30) -> dict:
    """Baseline statistical forecast from issue movement history (ERP-15)."""
    movements = intel_reads.list_item_movements(org_id, item_id=item_id, limit=365)
    issues = [
        abs(float(m.get("quantity") or 0))
        for m in movements
        if str(m.get("movement_type") or "").lower() in {"issue", "sale", "consumption"}
    ]
    if not issues:
        return {
            "item_id": item_id,
            "horizon_days": horizon_days,
            "predicted_quantity": 0.0,
            "confidence": 0.2,
            "model": "moving_average_v1",
            "sample_size": 0,
        }
    daily_avg = mean(issues)
    predicted = round(daily_avg * max(horizon_days, 1) / 30.0, 2)
    confidence = min(0.95, 0.3 + len(issues) * 0.02)
    return {
        "item_id": item_id,
        "horizon_days": horizon_days,
        "predicted_quantity": predicted,
        "confidence": round(confidence, 3),
        "model": "moving_average_v1",
        "sample_size": len(issues),
        "daily_issue_avg": round(daily_avg, 4),
    }
