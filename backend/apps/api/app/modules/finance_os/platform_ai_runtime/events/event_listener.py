from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GOAL_TRIGGER_MAP, goal_manager


def consume_goal_trigger(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    if event_type not in GOAL_TRIGGER_MAP:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from app.modules.platform.billing.billing_hooks import gate_ai_event

        if not gate_ai_event(org_id, feature="agents", operation_code="agent_execution"):
            return
    except Exception:
        pass
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    try:
        goal_manager.handle_event(org_id, event_type=event_type, payload=payload)
    except Exception:
        pass
