from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import ApprovalQueueItem, WorldState
from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service


GOAL_TRIGGER_MAP: dict[str, str] = {
    "invoice.due": "collections_followup",
    "invoice.anomaly_detected": "ap_review",
    "invoice.duplicate_detected": "ap_review",
    "liquidity_alert.created": "treasury_advisory",
    "treasury.risk.detected": "treasury_advisory",
    "erp.period.close.requested": "period_close",
    "reconciliation.exception.created": "recon_review",
    "grn.confirmed": "inventory_received",
    "scheduler.collections.daily": "collections_followup",
    "scheduler.treasury.daily": "treasury_advisory",
    "scheduler.compliance.daily": "compliance_review",
    "compliance.obligation.due": "compliance_review",
}

SCHEDULER_TEMPLATES = {
    "collections_followup": "Daily collections: list overdue AR and recommend follow-up workflows.",
    "treasury_advisory": "Daily treasury review: cash position, liquidity alerts, funding recommendations.",
    "compliance_review": "Daily compliance review: upcoming obligations and penalty exposure.",
    "period_close": "Run period close checklist across inventory, reconciliation, and fiscal modules.",
}


class GoalManager:
    def template_message(self, template_key: str, payload: dict) -> str:
        templates = {
            "collections_followup": "Follow up on overdue invoices and launch collection workflow if needed.",
            "ap_review": "Review AP invoice exception and recommend approval workflow.",
            "treasury_advisory": "Review liquidity risk and cash position; recommend actions.",
            "period_close": SCHEDULER_TEMPLATES["period_close"],
            "recon_review": "Investigate reconciliation exceptions and suggest matches.",
            "inventory_received": "Confirm inventory receipt completed; verify balances.",
            "compliance_review": SCHEDULER_TEMPLATES["compliance_review"],
        }
        base = templates.get(template_key, SCHEDULER_TEMPLATES.get(template_key, "Respond to platform event with read-only analysis first."))
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
    ) -> dict | None:
        if not runtime_service.schema_ready():
            return None
        existing = goal_repository.list_goals(org_id, status="active", limit=5)
        for g in existing:
            if g.get("title") == title[:200]:
                latest = goal_repository.get_latest_run(org_id, g["id"])
                if latest and latest.get("status") in {"running", "pending_approval", "blocked"}:
                    resp = runtime_service.resume_run(
                        org_id,
                        goal_id=g["id"],
                        run_id=latest["id"],
                        user_id=user_id,
                        roles=roles,
                        attrs={"user_id": user_id},
                    )
                    return resp.model_dump()
        resp = runtime_service.chat(
            org_id,
            message=message,
            user_id=user_id,
            roles=roles or ["tenant_admin"],
            attrs={"user_id": user_id, "trigger_type": trigger_type},
            world_state=world_state,
            human_approved=False,
        )
        return resp.model_dump()

    def handle_event(
        self,
        org_id: str,
        *,
        event_type: str,
        payload: dict,
        user_id: str = "event-runtime",
        roles: list[str] | None = None,
    ) -> dict | None:
        template_key = GOAL_TRIGGER_MAP.get(event_type)
        if not template_key:
            return None
        message = self.template_message(template_key, payload)
        return self.create_or_resume(
            org_id,
            title=message[:200],
            message=message,
            trigger_type="event",
            user_id=user_id,
            roles=roles,
        )

    def write_outcome_memory(self, org_id: str, *, goal_id: str, run_id: str, summary: str) -> None:
        try:
            from app.modules.finance_os.agents.services.agent_memory_service import write_outcome

            write_outcome(org_id, "platform_ai_runtime", run_id, summary)
        except Exception:
            pass

    def list_approval_queue(self, org_id: str) -> list[ApprovalQueueItem]:
        items: list[ApprovalQueueItem] = []
        for row in goal_repository.list_pending_runs(org_id):
            items.append(ApprovalQueueItem(
                source="m38",
                goal_id=row.get("goal_id"),
                goal_run_id=row.get("run_id"),
                title=str(row.get("title") or "M38 goal"),
                status=str(row.get("status") or ""),
                current_node_id=row.get("current_node_id"),
                risk_level=row.get("risk_level"),
                created_at=row.get("started_at"),
            ))
        try:
            from app.modules.finance_os.agents.repositories.execution_repository import execution_repository

            if execution_repository.schema_ready():
                for ex in execution_repository.list(org_id, status="pending_approval", limit=20):
                    items.append(ApprovalQueueItem(
                        source="m29",
                        execution_id=str(ex.get("id") or ""),
                        title=str(ex.get("agent_name") or "M29 agent run"),
                        status=str(ex.get("status") or ""),
                        created_at=str(ex.get("created_at") or ""),
                    ))
        except Exception:
            pass
        return items


goal_manager = GoalManager()
