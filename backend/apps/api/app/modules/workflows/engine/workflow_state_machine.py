"""Deterministic workflow instance lifecycle FSM."""

from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"queued", "cancelled"}),
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"waiting_approval", "executing", "completed", "failed", "cancelled", "escalated"}),
    "waiting_approval": frozenset({"approved", "rejected", "escalated", "cancelled", "timed_out"}),
    "approved": frozenset({"executing", "completed", "failed", "cancelled"}),
    "executing": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset({"queued", "running", "cancelled"}),
    "cancelled": frozenset(),
    "timed_out": frozenset({"escalated", "cancelled", "running"}),
    "escalated": frozenset({"waiting_approval", "running", "cancelled"}),
    "rejected": frozenset(),
}

TERMINAL_STATUSES = frozenset({"completed", "cancelled", "rejected"})


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Invalid workflow transition: {current} -> {target}")
        self.current = current
        self.target = target


def can_transition(current_status: str, target_status: str) -> bool:
    current = (current_status or "draft").strip().lower()
    target = (target_status or "").strip().lower()
    if current == target:
        return True
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    return target in allowed


def validate_transition(current_status: str, target_status: str) -> None:
    if not can_transition(current_status, target_status):
        raise InvalidTransitionError(current_status, target_status)


def legacy_state_to_status(legacy_state: str) -> str:
    mapping = {
        "pending": "running",
        "pending_approval": "waiting_approval",
        "blocked": "running",
        "executed": "completed",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mapping.get((legacy_state or "").strip().lower(), "running")


def status_to_legacy_state(status: str) -> str:
    mapping = {
        "waiting_approval": "pending_approval",
        "approved": "pending_approval",
        "executing": "running",
        "completed": "executed",
        "failed": "blocked",
        "escalated": "blocked",
        "rejected": "cancelled",
    }
    return mapping.get((status or "").strip().lower(), "running")
