"""Event-driven planner — continuous evaluation; never direct ERP mutation (Wave 5)."""

from __future__ import annotations

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.autonomy.governance import autonomy_governance
from app.modules.finance_os.platform_ai_runtime.autonomy.goal_memory import goal_memory
from app.modules.finance_os.platform_ai_runtime.autonomy.recommendation_engine import autonomy_recommendation_engine
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import EventPlanDecision
from app.services.logger import log_event

# Config-style subscription map: event → (template_key, default_action)
# Extends GOAL_TRIGGER_MAP without duplicating bus — consumers still use consume_goal_trigger.
EVENT_SUBSCRIPTIONS: dict[str, dict] = {
    "invoice.due": {"template": "collections_followup", "default": "prepare_workflow", "prepare": True},
    "invoice.anomaly_detected": {"template": "ap_review", "default": "recommend", "prepare": True},
    "invoice.duplicate_detected": {"template": "ap_review", "default": "approval_required", "prepare": True},
    "invoice.created": {"template": "ap_review", "default": "observe", "prepare": False},
    "payment.failed": {"template": "treasury_advisory", "default": "recommend", "prepare": True},
    "liquidity_alert.created": {"template": "treasury_advisory", "default": "recommend", "prepare": True},
    "treasury.risk.detected": {"template": "treasury_advisory", "default": "recommend", "prepare": True},
    "treasury.forecast.updated": {"template": "treasury_advisory", "default": "observe", "prepare": False},
    "bank.statement.imported": {"template": "recon_review", "default": "prepare_workflow", "prepare": True},
    "reconciliation.exception.created": {"template": "recon_review", "default": "prepare_workflow", "prepare": True},
    "erp.period.close.requested": {"template": "period_close", "default": "start_goal", "prepare": True},
    "grn.confirmed": {"template": "inventory_received", "default": "observe", "prepare": False},
    "expense.submitted": {"template": "ap_review", "default": "observe", "prepare": False},
    "compliance.obligation.due": {"template": "compliance_review", "default": "prepare_workflow", "prepare": True},
    "gst.due": {"template": "compliance_review", "default": "prepare_workflow", "prepare": True},
    "approval.pending": {"template": "ap_review", "default": "notify_user", "prepare": False},
    "vendor.overdue": {"template": "collections_followup", "default": "recommend", "prepare": True},
    "cash.below_threshold": {"template": "treasury_advisory", "default": "recommend", "prepare": True},
    "scheduler.collections.daily": {"template": "collections_followup", "default": "prepare_workflow", "prepare": True},
    "scheduler.treasury.daily": {"template": "treasury_advisory", "default": "prepare_workflow", "prepare": True},
    "scheduler.compliance.daily": {"template": "compliance_review", "default": "prepare_workflow", "prepare": True},
}


class EventDrivenPlanner:
    """Evaluates every subscribed event; produces decision + optional recommendation only."""

    def subscribed(self, event_type: str) -> bool:
        if event_type in EVENT_SUBSCRIPTIONS:
            return True
        # Back-compat: goal manager map
        from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GOAL_TRIGGER_MAP

        return event_type in GOAL_TRIGGER_MAP

    def evaluate(self, org_id: str, *, event_type: str, payload: dict) -> EventPlanDecision:
        if not getattr(settings, "m38_autonomy_enabled", True):
            return EventPlanDecision(action="ignore", event_type=event_type, reason="autonomy_disabled")

        sub = EVENT_SUBSCRIPTIONS.get(event_type)
        if not sub:
            from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GOAL_TRIGGER_MAP

            template = GOAL_TRIGGER_MAP.get(event_type)
            if not template:
                return EventPlanDecision(action="ignore", event_type=event_type, reason="unsubscribed")
            sub = {"template": template, "default": "start_goal", "prepare": True}

        template_key = str(sub["template"])
        entity_id = (
            payload.get("entity_id")
            or payload.get("invoice_id")
            or payload.get("payment_id")
            or payload.get("grn_id")
        )
        evidence = [
            f"event={event_type}",
            f"entity={entity_id}" if entity_id else "entity=none",
            f"template={template_key}",
        ]

        # Prefer resume over duplicate start
        existing = goal_memory.find_matching_goal(
            org_id,
            template_key=template_key,
            entity_id=str(entity_id) if entity_id else None,
            title_hint=None,
        )
        if existing:
            latest = goal_repository.get_latest_run(org_id, existing["id"])
            if latest and latest.get("status") in {
                "running",
                "pending_approval",
                "blocked",
                "paused",
            }:
                env = autonomy_governance.build_envelope(
                    reason=f"Resume long-running goal for {event_type}",
                    evidence=evidence,
                    confidence=0.85,
                    prep_only=True,
                    time_horizon="days",
                )
                return EventPlanDecision(
                    action="resume_goal",
                    event_type=event_type,
                    template_key=template_key,
                    reason="In-flight goal matches event — resume, do not restart completed nodes",
                    evidence=evidence,
                    confidence=0.85,
                    goal_id=existing["id"],
                    prep_only=True,
                    envelope=env,
                    collaboration_message=f"Resuming existing goal for {event_type} (no completed work restarted).",
                    notify=False,
                )

        action = str(sub.get("default") or "observe")
        # High risk events escalate to approval_required recommendation
        if event_type in {"invoice.duplicate_detected", "payment.failed", "cash.below_threshold"}:
            action = "approval_required" if action == "recommend" else action

        conf = 0.75 if sub.get("prepare") else 0.55
        env = autonomy_governance.build_envelope(
            reason=f"Event-driven plan for {event_type}",
            evidence=evidence,
            confidence=conf,
            prep_only=True,
            policies=["unified_policy_gate", "approval_engine"],
            business_impact=f"Autonomous continuous ops for {template_key}",
            time_horizon="days",
        )
        rec = autonomy_recommendation_engine.from_template(
            template_key,
            reason=f"Platform event {event_type} evaluated",
            evidence=evidence,
            confidence=conf,
            entity_id=str(entity_id) if entity_id else None,
        )

        decision = EventPlanDecision(
            action=action,  # type: ignore[arg-type]
            event_type=event_type,
            template_key=template_key,
            reason=f"Subscribed event → {action}",
            evidence=evidence,
            confidence=conf,
            prep_only=True,
            envelope=env,
            recommendation=rec.model_dump(),
            collaboration_message=autonomy_recommendation_engine.collaboration_message(rec),
            notify=action in {"notify_user", "approval_required", "recommend"},
        )
        log_event(
            "m38.event_planner.decision",
            org_id=org_id,
            platform_event=event_type,
            action=decision.action,
            template=template_key,
        )
        return decision


event_driven_planner = EventDrivenPlanner()
