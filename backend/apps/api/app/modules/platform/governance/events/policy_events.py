from __future__ import annotations

from typing import Any


def emit_policy_approved(org_id: str, *, action: str, decision_id: str) -> None:
    _emit("policy.approved", org_id, {"action": action, "decision_id": decision_id})


def emit_policy_denied(org_id: str, *, action: str, reason: str) -> None:
    _emit("policy.denied", org_id, {"action": action, "reason": reason})


def emit_override_required(org_id: str, *, action: str, reason: str) -> None:
    _emit("policy.override.required", org_id, {"action": action, "reason": reason})


def emit_risk_detected(org_id: str, *, action: str, risk_level: str) -> None:
    _emit("policy.risk.detected", org_id, {"action": action, "risk_level": risk_level})


def emit_policy_evaluated(org_id: str, *, action: str, decision: str, decision_id: str | None) -> None:
    _emit("policy.evaluated", org_id, {"action": action, "decision": decision, "decision_id": decision_id})


def _emit(event_type: str, org_id: str, payload: dict[str, Any]) -> None:
    try:
        from app.services.event_bus import event_bus

        event_bus.publish(event_type=event_type, org_id=org_id, source="governance.policy_engine", payload=payload)
    except Exception:
        pass
