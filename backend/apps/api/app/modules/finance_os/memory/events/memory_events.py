from __future__ import annotations

from app.services.event_bus import event_bus

MEMORY_CREATED = "memory.created"
MEMORY_UPDATED = "memory.updated"
MEMORY_EXPIRED = "memory.expired"
MEMORY_HIGH_IMPORTANCE = "memory.high_importance.detected"
MEMORY_SUMMARIZED = "memory.summarized"


def _emit(event_type: str, org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source="finance_os.memory",
        trace_id=trace_id or "",
        payload=payload,
    )


def emit_memory_created(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(MEMORY_CREATED, org_id, payload, trace_id=trace_id)


def emit_memory_updated(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(MEMORY_UPDATED, org_id, payload, trace_id=trace_id)


def emit_memory_expired(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(MEMORY_EXPIRED, org_id, payload, trace_id=trace_id)


def emit_high_importance_detected(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(MEMORY_HIGH_IMPORTANCE, org_id, payload, trace_id=trace_id)


def emit_memory_summarized(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(MEMORY_SUMMARIZED, org_id, payload, trace_id=trace_id)
