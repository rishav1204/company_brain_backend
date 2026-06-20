from __future__ import annotations

from typing import Any

from app.services.event_bus import event_bus
from app.services.repositories import audit_repo


def _publish(
    *,
    event_type: str,
    org_id: str,
    source: str,
    trace_id: str | None,
    payload: dict[str, Any],
    principal: dict | None = None,
) -> None:
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source=source,
        trace_id=trace_id,
        payload=payload,
        principal=principal,
    )
    try:
        from app.modules.workflows.services.realtime_hub import workflow_realtime_hub

        workflow_realtime_hub.publish(org_id, {"event_type": event_type, "payload": payload, "trace_id": trace_id})
    except Exception:
        pass


def emit_workflow_created(org_id: str, instance_id: str, *, trace_id: str | None = None, extra: dict | None = None) -> None:
    _publish(
        event_type="workflow.created",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"workflow_instance_id": instance_id, **(extra or {})},
    )


def emit_workflow_started(org_id: str, instance_id: str, *, trace_id: str | None = None) -> None:
    _publish(event_type="workflow.started", org_id=org_id, source="workflow.engine", trace_id=trace_id, payload={"workflow_instance_id": instance_id})


def emit_workflow_completed(org_id: str, instance_id: str, *, trace_id: str | None = None) -> None:
    _publish(event_type="workflow.completed", org_id=org_id, source="workflow.engine", trace_id=trace_id, payload={"workflow_instance_id": instance_id})


def emit_workflow_failed(org_id: str, instance_id: str, reason: str, *, trace_id: str | None = None) -> None:
    _publish(
        event_type="workflow.failed",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"workflow_instance_id": instance_id, "reason": reason},
    )


def emit_workflow_escalated(
    org_id: str,
    instance_id: str,
    escalation_id: str,
    *,
    trace_id: str | None = None,
    escalated_to: str | None = None,
    escalation_type: str | None = None,
) -> None:
    payload: dict[str, Any] = {"workflow_instance_id": instance_id, "escalation_id": escalation_id}
    if escalated_to:
        payload["recipient_user_id"] = escalated_to
    if escalation_type:
        payload["reason"] = escalation_type
    _publish(
        event_type="workflow.escalated",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload=payload,
    )


def emit_approval_requested(
    org_id: str,
    approval_id: str,
    instance_id: str,
    *,
    trace_id: str | None = None,
    approver_user_id: str | None = None,
    approver_email: str | None = None,
    entity_label: str | None = None,
    amount: str | None = None,
) -> None:
    payload: dict[str, Any] = {"approval_id": approval_id, "workflow_instance_id": instance_id}
    if approver_user_id:
        payload["approver_user_id"] = approver_user_id
    if approver_email:
        payload["approver_email"] = approver_email
    if entity_label:
        payload["entity_label"] = entity_label
    if amount is not None:
        payload["amount"] = amount
    _publish(
        event_type="approval.requested",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload=payload,
    )


def emit_approval_completed(org_id: str, approval_id: str, decision: str, *, trace_id: str | None = None) -> None:
    _publish(
        event_type="approval.completed",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"approval_id": approval_id, "decision": decision},
    )
    if str(decision).lower() == "approved":
        emit_workflow_approved(org_id, approval_id, trace_id=trace_id)


def emit_workflow_approved(org_id: str, approval_id: str, *, trace_id: str | None = None) -> None:
    _publish(
        event_type="workflow.approved",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"approval_id": approval_id},
    )


def emit_workflow_stage_entered(
    org_id: str,
    *,
    workflow_instance_id: str,
    step_id: str,
    step_key: str,
    trace_id: str | None = None,
) -> None:
    _publish(
        event_type="workflow.stage.entered",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={
            "workflow_instance_id": workflow_instance_id,
            "step_id": step_id,
            "step_key": step_key,
        },
    )


def emit_workflow_stage_completed(
    org_id: str,
    *,
    workflow_instance_id: str,
    step_id: str,
    step_key: str,
    duration_ms: int | None = None,
    trace_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "workflow_instance_id": workflow_instance_id,
        "step_id": step_id,
        "step_key": step_key,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    _publish(
        event_type="workflow.stage.completed",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload=payload,
    )


def emit_approval_rejected(org_id: str, approval_id: str, *, trace_id: str | None = None) -> None:
    _publish(
        event_type="approval.rejected",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"approval_id": approval_id},
    )


def emit_workflow_advance_requested(
    org_id: str,
    instance_id: str,
    *,
    decided_level: int,
    approval_id: str,
    trace_id: str | None = None,
) -> None:
    _publish(
        event_type="workflow.advance.requested",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={
            "workflow_instance_id": instance_id,
            "decided_level": decided_level,
            "approval_id": approval_id,
        },
    )


def emit_sla_breached(org_id: str, instance_id: str, step_id: str | None, *, trace_id: str | None = None) -> None:
    _publish(
        event_type="sla.breached",
        org_id=org_id,
        source="workflow.engine",
        trace_id=trace_id,
        payload={"workflow_instance_id": instance_id, "step_id": step_id},
    )


def audit_transition(
    *,
    org_id: str,
    actor_id: str,
    instance_id: str,
    from_status: str,
    to_status: str,
    detail: dict | None = None,
) -> None:
    try:
        from app.modules.platform.governance.services.audit_service import audit_service

        from app.modules.platform.governance.utils.object_ref import format_workflow_ref

        audit_service.record(
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            action="workflow.transition",
            object_ref=format_workflow_ref(instance_id),
            entity_type="workflow_instance",
            entity_id=instance_id,
            before_state={"status": from_status},
            after_state={"status": to_status},
            payload={"from": from_status, "to": to_status, **(detail or {})},
            source_service="workflow.engine",
        )
    except Exception:
        audit_repo.create_log(
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            event_type="workflow.transition",
            object_ref=f"workflow_instance:{instance_id}",
            payload_jsonb={"from": from_status, "to": to_status, **(detail or {})},
        )
