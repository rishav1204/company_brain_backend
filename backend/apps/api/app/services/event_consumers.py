"""Event consumer facade — re-exports handlers for backward compatibility.

Wires finance_os + platform consumers including policy.evaluated materialization
via _consume_policy_events / _consume_audit_explorer_materialize.
"""
from __future__ import annotations

import app.services.event_consumers_handlers as _handlers
from app.services.action_service import execute_action
from app.services.event_bus import event_bus
from app.services.event_consumers_router import consume_event
from app.services.langgraph_runner import run_langgraph_flow
from app.modules.platform.billing.billing_hooks import gate_ai_event  # referenced by billing sync tests
from app.modules.platform.events.consumers.handlers.legacy_handlers import (
    _consume_audit_explorer_materialize,
    _consume_consolidation_events,
    _consume_policy_events,
    _publish_child_event,
)
from app.services.repositories import agents_repo

for _name in dir(_handlers):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(_handlers, _name)

# Explicit re-exports used by unit tests / static wiring checks
globals().setdefault("_consume_policy_events", _consume_policy_events)
globals().setdefault("_consume_audit_explorer_materialize", _consume_audit_explorer_materialize)
globals().setdefault("_consume_consolidation_events", _consume_consolidation_events)
globals().setdefault("_publish_child_event", _publish_child_event)

__all__ = [
    "consume_event",
    "gate_ai_event",
    "agents_repo",
    "execute_action",
    "event_bus",
    "run_langgraph_flow",
    "_consume_consolidation_events",
    "_consume_policy_events",
    "_consume_audit_explorer_materialize",
    "_publish_child_event",
]
