from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_gst_response_received(org_id: str, *, return_id: str, status: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="gst.response.received",
        org_id=org_id,
        source="integration.gst",
        entity_type="gst_return",
        entity_id=return_id,
        payload={"return_id": return_id, "status": status},
        trace_id=trace_id,
    )


def emit_webhook_received(org_id: str, *, payload: dict, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="webhook.received",
        org_id=org_id,
        source="integration.webhooks",
        payload=payload,
        trace_id=trace_id,
    )
