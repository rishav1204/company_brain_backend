from __future__ import annotations

from typing import Any


def emit_compliance_alert(org_id: str, *, compliance_type: str, status: str, event_id: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="compliance.alert.generated",
            org_id=org_id,
            source="governance.compliance",
            entity_type="compliance_event",
            entity_id=event_id,
            payload={"compliance_type": compliance_type, "status": status},
        )
    except Exception:
        return None


def emit_gst_deadline_approaching(
    org_id: str, *, deadline: str, compliance_type: str = "gst"
) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="gst.deadline.approaching",
            org_id=org_id,
            source="governance.compliance",
            payload={"deadline": deadline, "compliance_type": compliance_type},
        )
    except Exception:
        return None
