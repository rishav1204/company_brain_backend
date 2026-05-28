from __future__ import annotations

from app.modules.platform.events.validators.event_validator import validate_event_envelope, validate_org_access
from app.modules.platform.events.validators.payload_validator import validate_payload_size


def validate_incoming_event(envelope: dict, *, org_id: str) -> None:
    validate_event_envelope(envelope)
    validate_org_access(envelope, org_id)
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    validate_payload_size(payload)
