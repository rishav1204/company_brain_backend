from __future__ import annotations

from typing import Any


def emit_policy_violation(org_id: str, *, violation_id: str, violation_type: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="policy.violation.detected",
            org_id=org_id,
            source="governance.engine",
            entity_type="violation",
            entity_id=violation_id,
            payload={"violation_type": violation_type},
        )
    except Exception:
        return None
