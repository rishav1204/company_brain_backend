from __future__ import annotations

from app.modules.platform.events.queues.priority_queue import is_high_priority_event


UI_EVENT_TYPES = frozenset(
    {
        "workflow.created",
        "workflow.started",
        "workflow.completed",
        "workflow.failed",
        "workflow.escalated",
        "workflow.updated",
        "approval.requested",
        "approval.completed",
        "approval.rejected",
        "sla.breached",
        "payment.completed",
        "erp.payment.completed",
        "invoice.flagged",
        "erp.invoice.created",
    }
)


class PlatformRealtimeBridge:
    def push(self, org_id: str, event_type: str, envelope: dict) -> None:
        if event_type not in UI_EVENT_TYPES and not event_type.startswith(("workflow.", "approval.", "sla.")):
            if not is_high_priority_event(event_type):
                return
        try:
            from app.modules.workflows.services.realtime_hub import workflow_realtime_hub

            workflow_realtime_hub.publish(
                org_id,
                {
                    "event_type": event_type,
                    "payload": envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {},
                    "trace_id": envelope.get("trace_id"),
                    "entity_type": envelope.get("payload", {}).get("entity_type") if isinstance(envelope.get("payload"), dict) else None,
                    "entity_id": envelope.get("payload", {}).get("entity_id") if isinstance(envelope.get("payload"), dict) else None,
                },
            )
        except Exception:
            pass


platform_realtime_bridge = PlatformRealtimeBridge()
