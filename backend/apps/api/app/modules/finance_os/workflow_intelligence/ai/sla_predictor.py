from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.engine.sla_engine import breach_risk, format_eta, predict_completion


def predict_sla(payload: dict) -> dict:
    remaining = [float(x) for x in payload.get("remaining_stage_p95", [])]
    pending = int(payload.get("pending_approvals") or 0)
    avg_wait = float(payload.get("avg_approval_wait_seconds") or 3600)
    eta_seconds = predict_completion(
        remaining_stage_p95=remaining,
        pending_approvals=pending,
        avg_approval_wait_seconds=avg_wait,
    )
    due_at = payload.get("due_at")
    risk, conf = breach_risk(predicted_completion_seconds=eta_seconds, due_at=due_at)
    return {
        "predicted_completion_seconds": eta_seconds,
        "predicted_eta": format_eta(eta_seconds),
        "breach_risk": risk,
        "confidence_score": conf * 100,
    }
