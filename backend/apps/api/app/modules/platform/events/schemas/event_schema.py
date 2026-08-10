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
    # Wave 2 governance fields
    correlation_id: str | None = None
    request_id: str | None = None
    company_id: str | None = None
    partition_key: str | None = None
    ordering_key: str | None = None
    is_financial: bool = False

    def to_bus_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        meta = dict(data.get("metadata") or {})
        if data.get("correlation_id"):
            meta.setdefault("correlation_id", data["correlation_id"])
        if data.get("request_id"):
            meta.setdefault("request_id", data["request_id"])
        if data.get("company_id"):
            meta.setdefault("company_id", data["company_id"])
        if data.get("partition_key"):
            meta.setdefault("partition_key", data["partition_key"])
        if data.get("ordering_key"):
            meta.setdefault("ordering_key", data["ordering_key"])
        meta.setdefault("is_financial", bool(data.get("is_financial")))
        return {
            "event_id": data["event_id"],
            "event_type": data["event_type"],
            "schema_version": data["event_version"],
            "org_id": data["org_id"],
            "source": data["source"],
            "occurred_at": data["timestamp"],
            "trace_id": data["trace_id"] or "",
            "principal": data.get("principal") or {},
            "correlation_id": data.get("correlation_id") or meta.get("correlation_id"),
            "request_id": data.get("request_id") or meta.get("request_id"),
            "company_id": data.get("company_id") or meta.get("company_id"),
            "partition_key": data.get("partition_key") or meta.get("partition_key"),
            "ordering_key": data.get("ordering_key") or meta.get("ordering_key"),
            "is_financial": bool(data.get("is_financial")),
            "payload": {
                **data["payload"],
                "entity_type": data.get("entity_type"),
                "entity_id": data.get("entity_id"),
                "actor_id": data.get("actor_id"),
                "metadata": meta,
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
