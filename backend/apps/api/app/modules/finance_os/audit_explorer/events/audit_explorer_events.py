from __future__ import annotations

from app.services.event_bus import event_bus

AUDIT_TIMELINE_UPDATED = "audit.timeline.updated"
AUDIT_EVIDENCE_LINKED = "audit.evidence.linked"
AUDIT_AI_DECISION_RECORDED = "audit.ai_decision.recorded"


def emit_timeline_updated(org_id: str, *, timeline_id: str, object_type: str, object_id: str, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AUDIT_TIMELINE_UPDATED,
        org_id=org_id,
        source="finance_os.audit_explorer",
        trace_id=trace_id,
        payload={"timeline_id": timeline_id, "object_type": object_type, "object_id": object_id},
    )


def emit_evidence_linked(org_id: str, *, timeline_id: str, evidence_type: str, evidence_ref: str, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AUDIT_EVIDENCE_LINKED,
        org_id=org_id,
        source="finance_os.audit_explorer",
        trace_id=trace_id,
        payload={"timeline_id": timeline_id, "evidence_type": evidence_type, "evidence_ref": evidence_ref},
    )


def emit_ai_decision_recorded(org_id: str, *, trail_id: str, execution_id: str | None = None, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AUDIT_AI_DECISION_RECORDED,
        org_id=org_id,
        source="finance_os.audit_explorer",
        trace_id=trace_id,
        payload={"trail_id": trail_id, "execution_id": execution_id},
    )
