"""Formal command lifecycle states for ERP Command Bridge."""

from __future__ import annotations

from enum import Enum


class CommandLifecycle(str, Enum):
    REQUESTED = "requested"
    VALIDATED = "validated"
    AUTHORIZING = "authorizing"
    AUTHORIZED = "authorized"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    ROLLED_BACK = "rolled_back"


# Valid transitions (to allow testing / observability)
_ALLOWED: dict[CommandLifecycle, frozenset[CommandLifecycle]] = {
    CommandLifecycle.REQUESTED: frozenset(
        {
            CommandLifecycle.VALIDATED,
            CommandLifecycle.FAILED,
            CommandLifecycle.DUPLICATE,
            CommandLifecycle.REJECTED,
        }
    ),
    CommandLifecycle.VALIDATED: frozenset(
        {
            CommandLifecycle.AUTHORIZING,
            CommandLifecycle.FAILED,
        }
    ),
    CommandLifecycle.AUTHORIZING: frozenset(
        {
            CommandLifecycle.AUTHORIZED,
            CommandLifecycle.REJECTED,
            CommandLifecycle.FAILED,
        }
    ),
    CommandLifecycle.AUTHORIZED: frozenset(
        {
            CommandLifecycle.APPROVAL_PENDING,
            CommandLifecycle.APPROVED,
            CommandLifecycle.EXECUTING,
            CommandLifecycle.FAILED,
        }
    ),
    CommandLifecycle.APPROVAL_PENDING: frozenset(
        {
            CommandLifecycle.APPROVED,
            CommandLifecycle.REJECTED,
            CommandLifecycle.FAILED,
        }
    ),
    CommandLifecycle.APPROVED: frozenset(
        {
            CommandLifecycle.EXECUTING,
            CommandLifecycle.FAILED,
        }
    ),
    CommandLifecycle.EXECUTING: frozenset(
        {
            CommandLifecycle.EXECUTED,
            CommandLifecycle.FAILED,
            CommandLifecycle.ROLLED_BACK,
        }
    ),
    CommandLifecycle.EXECUTED: frozenset(),
    CommandLifecycle.FAILED: frozenset({CommandLifecycle.ROLLED_BACK}),
    CommandLifecycle.REJECTED: frozenset(),
    CommandLifecycle.DUPLICATE: frozenset(),
    CommandLifecycle.ROLLED_BACK: frozenset(),
}


def can_transition(current: CommandLifecycle, nxt: CommandLifecycle) -> bool:
    return nxt in _ALLOWED.get(current, frozenset())
