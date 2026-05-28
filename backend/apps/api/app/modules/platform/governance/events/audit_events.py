from __future__ import annotations

from typing import Any


def emit_audit_log_created(org_id: str, *, audit_id: str, action: str, object_ref: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="audit.log.created",
            org_id=org_id,
            source="governance.audit",
            entity_type="audit_log",
            entity_id=audit_id,
            payload={"audit_id": audit_id, "action": action, "object_ref": object_ref},
        )
    except Exception:
        return None
