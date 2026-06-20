from __future__ import annotations

from app.services.event_bus import event_bus

GRAPH_UPDATED = "graph.updated"
GRAPH_LINEAGE_GENERATED = "graph.lineage.generated"
GRAPH_DEPENDENCY_DETECTED = "graph.dependency.detected"
GRAPH_ROOT_CAUSE_GENERATED = "graph.root_cause.generated"


def _emit(event_type: str, org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source="finance_os.graph",
        trace_id=trace_id or "",
        payload=payload,
    )


def emit_graph_updated(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(GRAPH_UPDATED, org_id, payload, trace_id=trace_id)


def emit_lineage_generated(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(GRAPH_LINEAGE_GENERATED, org_id, payload, trace_id=trace_id)


def emit_dependency_detected(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(GRAPH_DEPENDENCY_DETECTED, org_id, payload, trace_id=trace_id)


def emit_root_cause_generated(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    _emit(GRAPH_ROOT_CAUSE_GENERATED, org_id, payload, trace_id=trace_id)
