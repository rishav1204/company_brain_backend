from __future__ import annotations

from app.services.event_consumers import (
    _consume_workflow_approval_event,
    _consume_workflow_escalation_event,
    _consume_workflow_execution_event,
    _consume_workflow_sla_event,
)


def process_workflow_queue(queue: str, envelope: dict) -> None:
    if queue.endswith("workflow.execution") or queue.endswith("workflow.retries"):
        _consume_workflow_execution_event(envelope)
    elif queue.endswith("workflow.approvals"):
        _consume_workflow_approval_event(envelope)
    elif queue.endswith("workflow.sla"):
        _consume_workflow_sla_event(envelope)
    elif queue.endswith("workflow.escalations"):
        _consume_workflow_escalation_event(envelope)
