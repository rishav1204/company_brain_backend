from __future__ import annotations

from app.services.event_bus import event_bus

WORKFLOW_BOTTLENECK_DETECTED = "workflow.bottleneck.detected"
WORKFLOW_SLA_RISK_DETECTED = "workflow.sla_risk.detected"
WORKFLOW_OPTIMIZATION_RECOMMENDED = "workflow.optimization.recommended"
WORKFLOW_HEALTH_UPDATED = "workflow.health.updated"
WORKFLOW_INTELLIGENCE_COMPLETED = "workflow.intelligence.completed"


def _emit(event_type: str, org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source="finance_os.workflow_intelligence",
        trace_id=trace_id or "",
        payload=payload,
    )


def emit_bottleneck_detected(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(WORKFLOW_BOTTLENECK_DETECTED, org_id, payload, trace_id=trace_id)


def emit_sla_risk_detected(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(WORKFLOW_SLA_RISK_DETECTED, org_id, payload, trace_id=trace_id)


def emit_optimization_recommended(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(WORKFLOW_OPTIMIZATION_RECOMMENDED, org_id, payload, trace_id=trace_id)


def emit_health_updated(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(WORKFLOW_HEALTH_UPDATED, org_id, payload, trace_id=trace_id)


def emit_intelligence_completed(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(WORKFLOW_INTELLIGENCE_COMPLETED, org_id, payload, trace_id=trace_id)
