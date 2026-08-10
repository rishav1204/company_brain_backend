from __future__ import annotations

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner import (
    EVENT_SUBSCRIPTIONS,
    event_driven_planner,
)
from app.modules.finance_os.platform_ai_runtime.autonomy.goal_memory import goal_memory
from app.modules.finance_os.platform_ai_runtime.autonomy.recommendation_engine import autonomy_recommendation_engine
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    ApprovalQueueItem,
    GoalObjective,
    OperationalGoalRequest,
    WorldState,
)
from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service
from app.services.logger import log_event


GOAL_TRIGGER_MAP: dict[str, str] = {
    "invoice.due": "collections_followup",
    "invoice.anomaly_detected": "ap_review",
    "invoice.duplicate_detected": "ap_review",
    "invoice.created": "ap_review",
    "payment.failed": "treasury_advisory",
    "liquidity_alert.created": "treasury_advisory",
    "treasury.risk.detected": "treasury_advisory",
    "treasury.forecast.updated": "treasury_advisory",
    "erp.period.close.requested": "period_close",
    "reconciliation.exception.created": "recon_review",
    "bank.statement.imported": "recon_review",
    "grn.confirmed": "inventory_received",
    "expense.submitted": "ap_review",
    "approval.pending": "ap_review",
    "vendor.overdue": "collections_followup",
    "cash.below_threshold": "treasury_advisory",
    "gst.due": "compliance_review",
    "scheduler.collections.daily": "collections_followup",
    "scheduler.treasury.daily": "treasury_advisory",
    "scheduler.compliance.daily": "compliance_review",
    "compliance.obligation.due": "compliance_review",
}

# Keep EVENT_SUBSCRIPTIONS as source for new events; map covers back-compat.
for _et, _cfg in EVENT_SUBSCRIPTIONS.items():
    GOAL_TRIGGER_MAP.setdefault(_et, str(_cfg.get("template") or "ap_review"))

SCHEDULER_TEMPLATES = {
    "collections_followup": "Daily collections: list overdue AR and recommend follow-up workflows.",
    "treasury_advisory": "Daily treasury review: cash position, liquidity alerts, funding recommendations.",
    "compliance_review": "Daily compliance review: upcoming obligations and penalty exposure.",
    "period_close": "Run period close checklist across inventory, reconciliation, and fiscal modules.",
    "recon_review": "Prepare reconciliation matches for unmatched bank items (draft only).",
    "ap_review": "Prepare AP exception review pack (draft only).",
    "inventory_received": "Verify inventory receipt context after GRN confirm.",
}


class GoalManager:
    """Long-running goal lifecycle + event reactions (Wave 5). Planner never executes here."""

    def template_message(self, template_key: str, payload: dict, *, prep_only: bool = True) -> str:
        templates = {
            "collections_followup": "Follow up on overdue invoices and prepare collection workflow (no execution).",
            "ap_review": "Review AP invoice exception and prepare approval package (no mutation).",
            "treasury_advisory": "Review liquidity risk and cash position; prepare treasury recommendations.",
            "period_close": SCHEDULER_TEMPLATES["period_close"],
            "recon_review": "Investigate reconciliation exceptions and prepare proposed matches.",
            "inventory_received": "Confirm inventory receipt context; verify balances (read-only).",
            "compliance_review": SCHEDULER_TEMPLATES["compliance_review"],
        }
        base = templates.get(template_key, SCHEDULER_TEMPLATES.get(template_key, "Observe platform event — prepare analysis first."))
        if prep_only:
            base = f"[PREP-ONLY] {base}"
        entity_id = payload.get("entity_id") or payload.get("invoice_id") or payload.get("grn_id") or ""
        if entity_id:
            return f"{base} Entity: {entity_id}"
        return base

    def create_or_resume(
        self,
        org_id: str,
        *,
        title: str,
        message: str,
        trigger_type: str = "scheduler",
        user_id: str = "goal-manager",
        roles: list[str] | None = None,
        world_state: WorldState | None = None,
        prep_only: bool = True,
        template_key: str | None = None,
        goal_type: str = "operational",
        goal_id: str | None = None,
    ) -> dict | None:
        if not runtime_service.schema_ready():
            return None
        # Targeted resume
        if goal_id:
            latest = goal_repository.get_latest_run(org_id, goal_id)
            if latest and latest.get("status") in {"running", "pending_approval", "blocked", "paused"}:
                resp = runtime_service.resume_run(
                    org_id,
                    goal_id=goal_id,
                    run_id=latest["id"],
                    user_id=user_id,
                    roles=roles,
                    attrs={"user_id": user_id, "prep_only": prep_only},
                )
                return resp.model_dump()

        matched = goal_memory.find_matching_goal(
            org_id,
            title_hint=title[:200],
            template_key=template_key,
            entity_id=(world_state.screen.entity_id if world_state and world_state.screen else None),
        )
        if matched:
            latest = goal_repository.get_latest_run(org_id, matched["id"])
            if latest and latest.get("status") in {"running", "pending_approval", "blocked", "paused"}:
                resp = runtime_service.resume_run(
                    org_id,
                    goal_id=matched["id"],
                    run_id=latest["id"],
                    user_id=user_id,
                    roles=roles,
                    attrs={"user_id": user_id, "prep_only": prep_only},
                )
                return resp.model_dump()

        existing = goal_repository.list_goals(org_id, status="active", limit=10)
        for g in existing:
            if g.get("title") == title[:200]:
                latest = goal_repository.get_latest_run(org_id, g["id"])
                if latest and latest.get("status") in {"running", "pending_approval", "blocked", "paused"}:
                    resp = runtime_service.resume_run(
                        org_id,
                        goal_id=g["id"],
                        run_id=latest["id"],
                        user_id=user_id,
                        roles=roles,
                        attrs={"user_id": user_id, "prep_only": prep_only},
                    )
                    return resp.model_dump()

        resp = runtime_service.chat(
            org_id,
            message=message,
            user_id=user_id,
            roles=roles or ["tenant_admin"],
            attrs={
                "user_id": user_id,
                "trigger_type": trigger_type,
                "prep_only": prep_only,
                "goal_type": goal_type,
                "template_key": template_key,
            },
            world_state=world_state,
            human_approved=False,
            prep_only=prep_only,
        )
        data = resp.model_dump()
        # Stamp trigger_config for event resume
        gid = data.get("goal_id")
        if gid and template_key:
            try:
                goal_repository.update_trigger_config(
                    org_id,
                    gid,
                    {"template_key": template_key, "trigger_type": trigger_type, "prep_only": prep_only},
                )
            except Exception as exc:
                log_event("m38.goal.trigger_config_failed", org_id=org_id, detail=str(exc))
        return data

    def handle_event(
        self,
        org_id: str,
        *,
        event_type: str,
        payload: dict,
        user_id: str = "event-runtime",
        roles: list[str] | None = None,
    ) -> dict | None:
        """Event path: evaluate → plan decision only; execute only via runtime with policy gates."""
        decision = event_driven_planner.evaluate(org_id, event_type=event_type, payload=payload)
        if decision.action == "ignore":
            log_event("m38.goal.event_ignored", org_id=org_id, platform_event=event_type)
            return {"decision": decision.model_dump(), "status": "ignored"}

        template_key = decision.template_key or GOAL_TRIGGER_MAP.get(event_type) or "ap_review"
        message = self.template_message(template_key, payload, prep_only=decision.prep_only)

        if decision.action == "observe":
            # Soft recommendation only — no goal run
            rec = decision.recommendation
            log_event("m38.goal.event_observe", org_id=org_id, platform_event=event_type)
            return {
                "decision": decision.model_dump(),
                "status": "observed",
                "recommendation": rec,
                "collaboration_message": decision.collaboration_message,
            }

        if decision.action in {"recommend", "notify_user", "approval_required"}:
            # Produce recommend + optional light prep goal
            if decision.action == "recommend" and not getattr(settings, "m38_autonomy_start_goals", True):
                return {
                    "decision": decision.model_dump(),
                    "status": "recommended",
                    "recommendation": decision.recommendation,
                    "collaboration_message": decision.collaboration_message,
                }

        if decision.action == "resume_goal" and decision.goal_id:
            return self.create_or_resume(
                org_id,
                title=message[:200],
                message=message,
                trigger_type="event",
                user_id=user_id,
                roles=roles,
                prep_only=True,
                template_key=template_key,
                goal_id=decision.goal_id,
            )

        # start_goal | prepare_workflow | approval_required / recommend with goal
        out = self.create_or_resume(
            org_id,
            title=message[:200],
            message=message,
            trigger_type="event",
            user_id=user_id,
            roles=roles,
            prep_only=True,  # financial truth never auto-mutates
            template_key=template_key,
            goal_type="operational",
        )
        if out is not None:
            out["decision"] = decision.model_dump()
            out["collaboration_message"] = decision.collaboration_message
            if decision.recommendation and out.get("goal_run_id"):
                try:
                    from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import AutonomyRecommendation

                    rec = AutonomyRecommendation(**decision.recommendation)
                    autonomy_recommendation_engine.persist_soft(
                        org_id, run_id=str(out["goal_run_id"]), rec=rec
                    )
                except Exception as exc:
                    log_event("m38.goal.recommendation_persist_failed", detail=str(exc))
        return out

    def create_operational_goal(
        self,
        org_id: str,
        request: OperationalGoalRequest,
        *,
        user_id: str,
        roles: list[str] | None = None,
    ) -> dict:
        """Long-running multi-day/week goal with objectives (survives restarts via DB)."""
        ws = request.world_state or WorldState()
        if request.objectives:
            ws = goal_memory.attach_objectives(
                ws, list(request.objectives), financial_targets=request.financial_targets
            )
        elif request.financial_targets:
            ws = goal_memory.attach_objectives(ws, [], financial_targets=request.financial_targets)

        message = request.description or request.title
        if request.prep_only:
            message = f"[PREP-ONLY][HORIZON={request.horizon}] {message}"
        resp = runtime_service.chat(
            org_id,
            message=message,
            user_id=user_id,
            roles=roles,
            world_state=ws,
            human_approved=False,
            prep_only=request.prep_only,
            attrs={
                "goal_type": "operational",
                "horizon": request.horizon,
                "prep_only": request.prep_only,
                "trigger_config": request.trigger_config,
            },
        )
        data = resp.model_dump()
        if data.get("goal_id"):
            goal_repository.update_trigger_config(
                org_id,
                data["goal_id"],
                {
                    **(request.trigger_config or {}),
                    "horizon": request.horizon,
                    "prep_only": request.prep_only,
                    "operational": True,
                },
            )
            if request.objectives:
                # Normalize objective ids link
                for o in request.objectives:
                    if data["goal_id"] not in o.linked_goal_ids:
                        o.linked_goal_ids.append(data["goal_id"])
        return data

    def write_outcome_memory(self, org_id: str, *, goal_id: str, run_id: str, summary: str) -> None:
        objectives = goal_memory.summarize_for_planner(org_id)
        goal_memory.remember_outcome(
            org_id, goal_id=goal_id, run_id=run_id, summary=summary, objectives=objectives
        )
        try:
            from app.modules.finance_os.agents.services.agent_memory_service import write_outcome

            write_outcome(org_id, "platform_ai_runtime", run_id, summary if len(summary) >= 20 else summary + " completed")
        except Exception:
            pass

    def list_approval_queue(self, org_id: str) -> list[ApprovalQueueItem]:
        items: list[ApprovalQueueItem] = []
        for row in goal_repository.list_pending_runs(org_id):
            items.append(
                ApprovalQueueItem(
                    source="m38",
                    goal_id=row.get("goal_id"),
                    goal_run_id=row.get("run_id"),
                    title=str(row.get("title") or "M38 goal"),
                    status=str(row.get("status") or ""),
                    current_node_id=row.get("current_node_id"),
                    risk_level=row.get("risk_level"),
                    created_at=row.get("started_at"),
                )
            )
        try:
            from app.modules.finance_os.agents.repositories.execution_repository import execution_repository

            if execution_repository.schema_ready():
                for ex in execution_repository.list(org_id, status="pending_approval", limit=20):
                    items.append(
                        ApprovalQueueItem(
                            source="m29",
                            execution_id=str(ex.get("id") or ""),
                            title=str(ex.get("agent_name") or "M29 agent run"),
                            status=str(ex.get("status") or ""),
                            created_at=str(ex.get("created_at") or ""),
                        )
                    )
        except Exception:
            pass
        return items

    def progress_snapshot(self, org_id: str, goal_id: str) -> dict | None:
        goal = goal_repository.get_goal(org_id, goal_id)
        if not goal:
            return None
        run = goal_repository.get_latest_run(org_id, goal_id)
        graph_row = goal_repository.get_latest_graph(org_id, run["id"]) if run else None
        completed, pending = [], []
        if graph_row and isinstance(graph_row.get("nodes"), list):
            for n in graph_row["nodes"]:
                if not isinstance(n, dict):
                    continue
                if n.get("status") in {"completed", "skipped"}:
                    completed.append(n.get("id"))
                elif n.get("status") in {"pending", "running"}:
                    pending.append(n.get("id"))
        total = max(len(completed) + len(pending), 1)
        meta = (run or {}).get("metadata") or {}
        return {
            "goal_id": goal_id,
            "run_id": (run or {}).get("id"),
            "current_node_id": (run or {}).get("current_node_id"),
            "completed_nodes": completed,
            "pending_nodes": pending,
            "approval_state": (run or {}).get("status"),
            "checkpoint": meta.get("checkpoint") if isinstance(meta, dict) else None,
            "progress_percent": round(100.0 * len(completed) / total, 1),
            "risk_level": (run or {}).get("risk_level"),
            "estimated_completion": (goal.get("plan_metadata") or {}).get("estimated_completion")
            if isinstance(goal.get("plan_metadata"), dict)
            else None,
            "steps_completed": meta.get("steps_completed", 0) if isinstance(meta, dict) else 0,
        }


goal_manager = GoalManager()
