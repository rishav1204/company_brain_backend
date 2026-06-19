from __future__ import annotations

from typing import Any

# event_type -> (notification_type, priority, channels)
EVENT_NOTIFICATION_MAP: dict[str, tuple[str, str, list[str]]] = {
    "approval.requested": ("approval_request", "high", ["in_app", "email"]),
    "workflow.approval.reminder": ("approval_request", "medium", ["in_app", "email"]),
    "approval.completed": ("workflow_update", "medium", ["in_app"]),
    "approval.rejected": ("workflow_update", "medium", ["in_app"]),
    "workflow.escalated": ("workflow_escalation", "high", ["in_app", "email", "slack"]),
    "workflow.step.notification": ("workflow_update", "medium", ["in_app", "email"]),
    "workflow.advance.requested": ("approval_request", "high", ["in_app", "email"]),
    "sla.breached": ("sla_breach", "high", ["in_app", "email"]),
    "policy.violation.detected": ("compliance_alert", "critical", ["in_app", "email"]),
    "compliance.alert.generated": ("compliance_alert", "high", ["in_app", "email"]),
    "payment.risk.detected": ("risk_alert", "critical", ["in_app", "email"]),
    "risk.detected": ("risk_alert", "high", ["in_app", "email"]),
    "suspicious.activity.detected": ("risk_alert", "critical", ["in_app", "email", "slack"]),
    "invoice.approval.required": ("invoice_approval_request", "high", ["in_app", "email"]),
    "gst.deadline.approaching": ("gst_deadline_alert", "high", ["in_app", "email"]),
    "ai.reconciliation.suggested": ("system_alert", "medium", ["in_app", "email"]),
    "payment.executed": ("payment_completed", "high", ["in_app", "email"]),
    "bank.transaction.imported": ("system_alert", "medium", ["in_app"]),
    "reconciliation.completed": ("system_alert", "medium", ["in_app", "email"]),
    "cash.position.updated": ("system_alert", "low", ["in_app"]),
    "erp.reconciliation.pending": ("system_alert", "medium", ["in_app", "email"]),
    "invoice.ai.reviewed": ("system_alert", "medium", ["in_app"]),
    "erp.payment.completed": ("payment_completed", "medium", ["in_app", "email"]),
    "erp.payment.failed": ("payment_alert", "high", ["in_app", "email"]),
    "erp.invoice.created": ("workflow_update", "low", ["in_app"]),
    "erp.gst.return.generated": ("compliance_alert", "medium", ["in_app", "email"]),
    "gst.transaction.recorded": ("system_alert", "low", ["in_app"]),
    "gst.mismatch.detected": ("compliance_alert", "high", ["in_app", "email"]),
    "tds.calculated": ("system_alert", "medium", ["in_app"]),
    "irn.generated": ("system_alert", "medium", ["in_app", "email"]),
    "eway.bill.created": ("system_alert", "medium", ["in_app"]),
    "document.uploaded": ("system_alert", "low", ["in_app"]),
    "ocr.completed": ("workflow_update", "medium", ["in_app"]),
    "document.classified": ("workflow_update", "low", ["in_app"]),
    "duplicate.detected": ("risk_alert", "high", ["in_app", "email"]),
    "job.failed": ("system_alert", "high", ["in_app"]),
    "retry.exceeded": ("system_alert", "critical", ["in_app", "email"]),
    "scheduler.reconciliation.daily": ("system_alert", "low", ["in_app"]),
}


def resolve_notification_plan(event_type: str) -> tuple[str, str, list[str]] | None:
    if event_type in EVENT_NOTIFICATION_MAP:
        return EVENT_NOTIFICATION_MAP[event_type]
    if event_type.startswith("workflow."):
        return ("workflow_update", "medium", ["in_app"])
    if event_type.startswith("erp."):
        return ("system_alert", "medium", ["in_app"])
    if event_type.startswith("gst."):
        return ("gst_deadline_alert", "high", ["in_app", "email"])
    return None


def build_template_variables(envelope: dict) -> dict[str, Any]:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    return {
        "recipient_name": payload.get("recipient_name") or payload.get("approver_name") or "User",
        "entity_label": payload.get("entity_label") or payload.get("invoice_id") or envelope.get("entity_id", "item"),
        "amount": payload.get("amount", ""),
        "workflow_id": payload.get("workflow_instance_id") or payload.get("workflow_id", ""),
        "reason": payload.get("reason", ""),
        "compliance_type": payload.get("compliance_type", ""),
        "status": payload.get("status", ""),
        "summary": payload.get("summary") or payload.get("risk", ""),
        "invoice_number": payload.get("invoice_number") or payload.get("entity_label", ""),
        "deadline": payload.get("deadline", ""),
        "event_type": envelope.get("event_type", ""),
        "body": payload.get("message") or str(payload),
        "subject": payload.get("subject"),
        "locale": payload.get("locale", "en"),
    }


def extract_recipients(envelope: dict) -> list[dict[str, Any]]:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    recipients: list[dict[str, Any]] = []
    if payload.get("recipient_user_id"):
        recipients.append(
            {
                "user_id": str(payload["recipient_user_id"]),
                "email": payload.get("recipient_email"),
            }
        )
    if payload.get("approver_user_id"):
        recipients.append(
            {
                "user_id": str(payload["approver_user_id"]),
                "email": payload.get("approver_email"),
            }
        )
    if payload.get("requested_from"):
        recipients.append({"user_id": str(payload["requested_from"]), "email": payload.get("email")})
    if not recipients and envelope.get("actor_id"):
        recipients.append({"user_id": str(envelope["actor_id"]), "email": payload.get("email")})
    return recipients
