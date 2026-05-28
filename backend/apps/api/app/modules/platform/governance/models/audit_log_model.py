from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuditLogRecord:
    id: str
    org_id: str
    actor_id: str
    actor_type: str
    action: str
    event_type: str
    object_ref: str
    entity_type: str | None = None
    entity_id: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    payload_jsonb: dict[str, Any] | None = None
    request_id: str | None = None
    trace_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    source_service: str | None = None
    created_at: str | None = None
