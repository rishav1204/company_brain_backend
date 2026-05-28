from __future__ import annotations


def audit_notification_delivery(
    org_id: str,
    *,
    notification_id: str,
    channel: str,
    status: str,
    trace_id: str | None = None,
) -> None:
    try:
        from app.modules.platform.governance.services.audit_service import audit_service

        if not audit_service.schema_ready():
            return
        audit_service.record(
            org_id=org_id,
            actor_type="system",
            actor_id="notifications.engine",
            action=f"notification.{status}",
            object_ref=f"notification:{notification_id}",
            entity_type="notification",
            entity_id=notification_id,
            payload={"channel": channel, "status": status},
            trace_id=trace_id,
            source_service="notifications.engine",
            event_type=f"notification.{status}",
            skip_auto_audit_flag=True,
        )
    except Exception:
        pass
