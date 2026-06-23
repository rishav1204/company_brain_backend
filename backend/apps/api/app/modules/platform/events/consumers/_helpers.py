"""Shared helpers for domain event consumers."""
from __future__ import annotations

from app.services.event_bus import event_bus
from app.services.principal_context import principal_from_envelope


def publish_child_event(envelope: dict, event_type: str, org_id: str, source: str, payload: dict) -> None:
    principal = principal_from_envelope(envelope)
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source=source,
        trace_id=str(envelope.get("trace_id", "")),
        payload=payload,
        principal=principal,
    )
