from __future__ import annotations

from app.services.event_bus import event_bus


AGENT_STARTED = "agent.started"
AGENT_COMPLETED = "agent.completed"
AGENT_RECOMMENDATION_CREATED = "agent.recommendation.created"
AGENT_WORKFLOW_CREATED = "agent.workflow.created"


def emit_started(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AGENT_STARTED,
        org_id=org_id,
        source="finance_os.agents",
        trace_id=trace_id,
        payload=payload,
    )


def emit_completed(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AGENT_COMPLETED,
        org_id=org_id,
        source="finance_os.agents",
        trace_id=trace_id,
        payload=payload,
    )


def emit_recommendation_created(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AGENT_RECOMMENDATION_CREATED,
        org_id=org_id,
        source="finance_os.agents",
        trace_id=trace_id,
        payload=payload,
    )


def emit_workflow_created(org_id: str, payload: dict, *, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=AGENT_WORKFLOW_CREATED,
        org_id=org_id,
        source="finance_os.agents",
        trace_id=trace_id,
        payload=payload,
    )
