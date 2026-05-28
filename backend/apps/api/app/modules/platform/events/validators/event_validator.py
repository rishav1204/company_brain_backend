from __future__ import annotations

REQUIRED_FIELDS = ("event_id", "event_type", "org_id", "source")


def validate_event_envelope(envelope: dict) -> None:
    for field in REQUIRED_FIELDS:
        if not str(envelope.get(field, "")).strip():
            raise ValueError(f"Event envelope missing required field: {field}")
    event_type = str(envelope.get("event_type", ""))
    if "." not in event_type:
        raise ValueError("event_type must be namespaced (e.g. invoice.created)")


def validate_org_access(envelope: dict, org_id: str) -> None:
    if str(envelope.get("org_id", "")) != org_id:
        raise PermissionError("Event org_id does not match request context")
