from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.events.workflow_events import emit_sla_breached, emit_workflow_escalated
from app.modules.workflows.repositories import escalation_repo, step_repo, workflow_repo
from app.modules.workflows.services.sla_service import is_reminder_due, is_sla_breached
from app.modules.workflows.services.workflow_observability import record_escalation, record_sla_breach
from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator
from app.services.event_bus import event_bus


class EscalationService:
    def escalate_instance(
        self,
        *,
        org_id: str,
        instance_id: str,
        escalation_type: str,
        escalated_to: str | None = None,
        step_id: str | None = None,
        trace_id: str | None = None,
        bump_priority: bool = True,
    ) -> dict:
        instance = workflow_repo.get_instance(org_id, instance_id)
        if not instance:
            raise ValueError("Workflow instance not found")
        if not escalated_to:
            escalated_to = workflow_orchestrator.resolve_assignee_for_role(
                org_id, "finance_manager", instance_id=instance_id
            )
        esc = escalation_repo.create_escalation(
            org_id=org_id,
            workflow_instance_id=instance_id,
            escalation_type=escalation_type,
            escalated_to=escalated_to,
            step_id=step_id,
            metadata={"previous_status": instance.get("status")},
        )
        new_status = apply_transition(current_status=instance["status"], target_status="escalated")
        workflow_repo.update_instance_status(
            org_id,
            instance_id,
            new_status,
            priority="high" if bump_priority else None,
        )
        emit_workflow_escalated(
            org_id,
            instance_id,
            esc["id"],
            trace_id=trace_id,
            escalated_to=escalated_to,
            escalation_type=escalation_type,
        )
        record_escalation()
        return esc

    def process_sla_breaches(self, org_id: str, *, trace_id: str | None = None) -> list[dict]:
        breached: list[dict] = []
        instances = workflow_repo.list_instances(org_id, status="waiting_approval", limit=500)
        for inst in instances:
            instance_id = inst["id"]
            for step in step_repo.list_steps(org_id, instance_id):
                if step.get("status") not in {"pending", "open"}:
                    continue
                due_at = step.get("due_at")
                if not is_sla_breached(due_at):
                    continue
                esc = self.escalate_instance(
                    org_id=org_id,
                    instance_id=instance_id,
                    escalation_type="sla_breach",
                    step_id=step["id"],
                    trace_id=trace_id,
                )
                emit_sla_breached(org_id, instance_id, step["id"], trace_id=trace_id)
                record_sla_breach()
                breached.append(esc)
        return breached

    def process_reminders(self, org_id: str, *, trace_id: str | None = None) -> int:
        from app.modules.workflows.services.sla_service import compute_reminder_at

        sent = 0
        instances = workflow_repo.list_instances(org_id, status="waiting_approval", limit=500)
        for inst in instances:
            for step in step_repo.list_steps(org_id, inst["id"]):
                due_at = step.get("due_at")
                reminder_at = compute_reminder_at(due_at=due_at, org_id=org_id)
                if not is_reminder_due(reminder_at):
                    continue
                from app.modules.platform.notifications.services.recipient_resolver import resolve_user_contact

                assignee = str(inst.get("metadata", {}).get("assignee") or step.get("assigned_to") or "")
                contact = resolve_user_contact(org_id, assignee) if assignee else {}
                event_bus.publish(
                    event_type="workflow.approval.reminder",
                    org_id=org_id,
                    source="workflow.sla_reminder",
                    trace_id=trace_id,
                    payload={
                        "workflow_instance_id": inst["id"],
                        "step_key": step.get("step_key"),
                        "recipient_user_id": assignee or None,
                        "recipient_email": contact.get("email"),
                        "entity_label": f"Workflow {inst['id']}",
                        "message": f"Step {step.get('step_key')} due soon",
                    },
                )
                sent += 1
        return sent

    def process_pending_escalations(self, org_id: str, *, hours: int = 48, trace_id: str | None = None) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        escalated: list[dict] = []
        instances = workflow_repo.list_instances(org_id, status="waiting_approval", limit=500)
        for inst in instances:
            started = inst.get("started_at")
            if started and started > cutoff:
                continue
            esc = self.escalate_instance(
                org_id=org_id,
                instance_id=inst["id"],
                escalation_type="manager_escalation",
                trace_id=trace_id,
            )
            escalated.append(esc)
        return escalated

    def process_finance_escalations(self, org_id: str, *, trace_id: str | None = None) -> list[dict]:
        out: list[dict] = []
        instances = workflow_repo.list_instances(org_id, limit=500)
        for inst in instances:
            meta = inst.get("metadata") or {}
            amount = meta.get("amount")
            try:
                amount_f = float(amount) if amount is not None else 0.0
            except (TypeError, ValueError):
                amount_f = 0.0
            if amount_f < 100000:
                continue
            if inst.get("status") not in {"waiting_approval", "running", "executing", "escalated"}:
                continue
            out.append(
                self.escalate_instance(
                    org_id=org_id,
                    instance_id=inst["id"],
                    escalation_type="finance_escalation",
                    escalated_to=workflow_orchestrator.resolve_assignee_for_role(
                        org_id, "cfo", instance_id=inst["id"]
                    ),
                    trace_id=trace_id,
                )
            )
        return out

    def process_compliance_escalations(self, org_id: str, *, trace_id: str | None = None) -> list[dict]:
        out: list[dict] = []
        instances = workflow_repo.list_instances(org_id, limit=500)
        for inst in instances:
            meta = inst.get("metadata") or {}
            flags = meta.get("compliance_flags") or meta.get("compliance_issues") or []
            if isinstance(flags, str):
                flags = [flags]
            if not flags and not meta.get("requires_compliance_review"):
                continue
            if inst.get("status") not in {"waiting_approval", "running", "executing"}:
                continue
            out.append(
                self.escalate_instance(
                    org_id=org_id,
                    instance_id=inst["id"],
                    escalation_type="compliance_escalation",
                    escalated_to=workflow_orchestrator.resolve_assignee_for_role(
                        org_id, "compliance_officer", instance_id=inst["id"]
                    ),
                    trace_id=trace_id,
                )
            )
        return out

    def process_risk_escalations(self, org_id: str, *, trace_id: str | None = None) -> list[dict]:
        out: list[dict] = []
        instances = workflow_repo.list_instances(org_id, limit=500)
        for inst in instances:
            meta = inst.get("metadata") or {}
            if str(meta.get("vendor_risk", "")).upper() != "HIGH":
                continue
            if inst.get("status") not in {"waiting_approval", "running"}:
                continue
            out.append(
                self.escalate_instance(
                    org_id=org_id,
                    instance_id=inst["id"],
                    escalation_type="risk_escalation",
                    trace_id=trace_id,
                )
            )
        return out


escalation_service = EscalationService()
