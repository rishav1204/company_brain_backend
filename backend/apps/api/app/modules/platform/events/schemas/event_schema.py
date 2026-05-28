from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CanonicalEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    event_version: str = "v1"
    org_id: str
    entity_type: str | None = None
    entity_id: str | None = None
    source: str
    timestamp: str
    trace_id: str | None = None
    actor_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    topic: str | None = None
    principal: dict[str, Any] | None = None

    def to_bus_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        return {
            "event_id": data["event_id"],
            "event_type": data["event_type"],
            "schema_version": data["event_version"],
            "org_id": data["org_id"],
            "source": data["source"],
            "occurred_at": data["timestamp"],
            "trace_id": data["trace_id"] or "",
            "principal": data.get("principal") or {},
            "payload": {
                **data["payload"],
                "entity_type": data.get("entity_type"),
                "entity_id": data.get("entity_id"),
                "actor_id": data.get("actor_id"),
                "metadata": data.get("metadata") or {},
            },
            "topic": data.get("topic"),
        }


class PublishEventRequest(BaseModel):
    event_type: str
    org_id: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    entity_type: str | None = None
    entity_id: str | None = None
    trace_id: str | None = None
    actor_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ReplayEventsRequest(BaseModel):
    event_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    from_event_id: str | None = None
