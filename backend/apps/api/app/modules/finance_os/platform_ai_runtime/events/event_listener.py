from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GOAL_TRIGGER_MAP, goal_manager
from app.services.logger import log_event


def _envelope_meta(envelope: dict) -> dict:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    return {
        "correlation_id": str(envelope.get("correlation_id") or envelope.get("trace_id") or payload.get("correlation_id") or ""),
        "causation_id": str(envelope.get("causation_id") or envelope.get("event_id") or payload.get("causation_id") or ""),
        "execution_id": str(payload.get("execution_id") or envelope.get("execution_id") or ""),
        "goal_id": str(payload.get("goal_id") or envelope.get("goal_id") or ""),
        "organization_id": str(envelope.get("org_id") or ""),
        "timestamp": str(envelope.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        "retry_count": int(envelope.get("retry_count") or payload.get("retry_count") or 0),
        "event_type": str(envelope.get("event_type") or ""),
    }


def consume_goal_trigger(envelope: dict) -> None:
    """M38 event-driven goal trigger — never silent on failure (AI-08). Wave 5: evaluator first."""
    meta = _envelope_meta(envelope)
    event_type = meta["event_type"]
    # Wave 5: use event-driven planner subscription catalog (superset of GOAL_TRIGGER_MAP)
    from app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner import event_driven_planner

    if not event_driven_planner.subscribed(event_type) and event_type not in GOAL_TRIGGER_MAP:
        return
    org_id = meta["organization_id"]
    if not org_id:
        log_event("m38.event.skipped", reason="missing_org_id", **{k: meta[k] for k in ("event_type", "correlation_id")})
        return

    try:
        from app.modules.platform.billing.billing_hooks import gate_ai_event

        if not gate_ai_event(org_id, feature="agents", operation_code="agent_execution"):
            log_event(
                "m38.event.billing_blocked",
                org_id=org_id,
                event_type=event_type,
                correlation_id=meta["correlation_id"],
            )
            return
    except Exception as exc:
        log_event(
            "m38.event.billing_gate_failed",
            org_id=org_id,
            event_type=event_type,
            detail=str(exc),
            correlation_id=meta["correlation_id"],
        )
        if not settings.billing_fail_open_ai:
            return

    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    try:
        goal_manager.handle_event(
            org_id,
            event_type=event_type,
            payload={
                **payload,
                **{k: meta[k] for k in ("correlation_id", "causation_id", "retry_count") if meta.get(k)},
            },
        )
        log_event(
            "m38.event.goal_trigger_ok",
            org_id=org_id,
            event_type=event_type,
            correlation_id=meta["correlation_id"],
            retry_count=meta["retry_count"],
        )
    except Exception as exc:
        log_event(
            "m38.event.goal_trigger_failed",
            org_id=org_id,
            event_type=event_type,
            detail=str(exc),
            correlation_id=meta["correlation_id"],
            causation_id=meta["causation_id"],
            retry_count=meta["retry_count"],
            max_retries=settings.m38_event_max_retries,
        )
        if int(meta["retry_count"]) >= int(settings.m38_event_max_retries):
            log_event(
                "m38.event.goal_trigger_poison",
                org_id=org_id,
                event_type=event_type,
                correlation_id=meta["correlation_id"],
                retry_count=meta["retry_count"],
            )
        raise
