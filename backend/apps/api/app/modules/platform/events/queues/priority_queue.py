from __future__ import annotations

HIGH_PRIORITY_QUEUES = frozenset(
    {
        "workflow.approvals",
        "workflow.sla",
        "workflow.escalations",
        "notifications.dispatch",
    }
)


def apply_priority_route(queue: str) -> str:
    """High-priority events use the same queue name but may be prefixed in future."""
    return queue


def is_high_priority_event(event_type: str) -> bool:
    return event_type.startswith(("approval.", "sla.", "workflow.escalated", "workflow.advance"))
