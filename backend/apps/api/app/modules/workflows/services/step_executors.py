from __future__ import annotations

from typing import Any

from app.services.event_bus import event_bus
from app.services.repositories import audit_repo


def execute_step(
    *,
    org_id: str,
    instance: dict,
    step: dict,
    trace_id: str | None = None,
) -> dict[str, Any]:
    step_type = str(step.get("step_type") or "system_task")
    handlers = {
        "ai_review": _execute_ai_review,
        "human_approval": _execute_human_placeholder,
        "manager_approval": _execute_human_placeholder,
        "system_task": _execute_system_task,
        "notification": _execute_notification,
        "reconciliation": _execute_reconciliation,
        "validation": _execute_validation,
        "payment_execution": _execute_payment_execution,
    }
    handler = handlers.get(step_type, _execute_system_task)
    return handler(org_id=org_id, instance=instance, step=step, trace_id=trace_id)


def _execute_ai_review(*, org_id: str, instance: dict, step: dict, trace_id: str | None) -> dict:
    metadata = instance.get("metadata") or {}
    event_bus.publish(
        event_type="agent.run.requested",
        org_id=org_id,
        source="workflow.ai_review",
        trace_id=trace_id,
        payload={
            "agent_type": "workflow_assistant",
            "trigger_type": "workflow_step",
            "workflow_instance_id": instance["id"],
            "step_id": step["id"],
            "workflow_id": instance.get("legacy_workflow_id") or instance["id"],
            "review_type": metadata.get("review_type", "invoice_review"),
            "resume_event": "workflow.step.completed",
        },
    )
    audit_repo.create_log(
        org_id=org_id,
        actor_type="system",
        actor_id="workflow-engine",
        event_type="workflow.ai_review.requested",
        object_ref=f"workflow_instance:{instance['id']}",
        payload_jsonb={"step_id": step["id"]},
    )
    return {"status": "waiting_ai", "detail": "ai_review_pending_agent"}


def _execute_human_placeholder(**_kwargs: Any) -> dict:
    return {"status": "waiting", "detail": "human_approval_required"}


def _execute_system_task(*, org_id: str, instance: dict, step: dict, trace_id: str | None) -> dict:
    event_bus.publish(
        event_type="workflow.step.system_task",
        org_id=org_id,
        source="workflow.executor",
        trace_id=trace_id,
        payload={"workflow_instance_id": instance["id"], "step_key": step.get("step_key")},
    )
    return {"status": "completed", "detail": "system_task_executed"}


def _execute_notification(*, org_id: str, instance: dict, step: dict, trace_id: str | None) -> dict:
    event_bus.publish(
        event_type="workflow.step.notification",
        org_id=org_id,
        source="workflow.executor",
        trace_id=trace_id,
        payload={
            "workflow_instance_id": instance.get("id"),
            "step_key": step.get("step_key"),
            "workflow_type": instance.get("workflow_type"),
            "entity_label": f"{instance.get('workflow_type')} — {step.get('step_key')}",
            "message": f"Workflow step notification: {step.get('step_key')}",
        },
    )
    return {"status": "completed", "detail": "notification_event_emitted"}


def _execute_reconciliation(*, org_id: str, instance: dict, step: dict, trace_id: str | None) -> dict:
    event_bus.publish(
        event_type="workflow.step.reconciliation",
        org_id=org_id,
        source="workflow.executor",
        trace_id=trace_id,
        payload={"workflow_instance_id": instance["id"], "entity_id": instance.get("entity_id")},
    )
    return {"status": "completed", "detail": "reconciliation_triggered"}


def _execute_validation(*, org_id: str, instance: dict, step: dict, **_kwargs: Any) -> dict:
    metadata = instance.get("metadata") or {}
    if metadata.get("force_validation_fail"):
        return {"status": "failed", "detail": "validation_failed", "retryable": True}
    return {"status": "completed", "detail": "validation_passed"}


def _execute_payment_execution(*, org_id: str, instance: dict, step: dict, trace_id: str | None) -> dict:
    event_bus.publish(
        event_type="agent.action.executed",
        org_id=org_id,
        source="workflow.payment_execution",
        trace_id=trace_id,
        payload={
            "workflow_instance_id": instance["id"],
            "action": "execute_payment",
            "entity_id": instance.get("entity_id"),
        },
    )
    return {"status": "completed", "detail": "payment_execution_dispatched"}
