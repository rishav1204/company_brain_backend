from __future__ import annotations

from typing import Any

from app.modules.core.iam.repositories.role_repository import RoleRepository
from app.modules.workflows.engine.approval_chain import build_approval_chain, inject_conditional_approvers
from app.modules.workflows.engine.condition_evaluator import evaluate_condition, step_should_run
from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.engine.execution_planner import build_execution_plan, retry_policy_for_step
from app.modules.workflows.engine.branch_resolver import get_escalation_policies
from app.modules.workflows.engine.workflow_state_machine import TERMINAL_STATUSES
from app.modules.workflows.events import workflow_events
from app.modules.workflows.repositories import approval_repo, step_repo, task_repo, workflow_repo
from app.modules.workflows.repositories.workflow_uow import workflow_uow
from app.modules.workflows.services.assignment_service import assign_user, build_workload_map
from app.modules.workflows.services.realtime_hub import workflow_realtime_hub
from app.modules.workflows.services.sla_service import compute_sla_due_at
from app.modules.workflows.services.step_executors import execute_step
from app.modules.workflows.services.workflow_observability import record_transition, workflow_span

_role_repo = RoleRepository()


class WorkflowOrchestrator:
    def _definition_for_instance(self, org_id: str, instance: dict) -> dict:
        def_id = instance.get("workflow_definition_id")
        if def_id:
            with __import__("app.services.db", fromlist=["get_db_conn"]).get_db_conn() as conn:
                from app.services.db import set_rls_org

                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT definition_json FROM workflow.workflow_definitions WHERE id = %s::uuid",
                        (def_id,),
                    )
                    row = cur.fetchone()
                    if row and row.get("definition_json"):
                        raw = row["definition_json"]
                        return raw if isinstance(raw, dict) else {}
        wtype = instance.get("workflow_type") or ""
        row = workflow_repo.get_definition_by_key(org_id, wtype)
        if row:
            raw = row.get("definition_json")
            return raw if isinstance(raw, dict) else {}
        return {}

    def _publish_realtime(self, org_id: str, event_type: str, payload: dict) -> None:
        workflow_realtime_hub.publish(
            org_id,
            {"event_type": event_type, "payload": payload},
        )

    def resolve_assignee_for_role(
        self,
        org_id: str,
        role_name: str,
        *,
        instance_id: str,
        definition: dict | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        users = _role_repo.list_users_by_role_name(org_id, role_name)
        if not users:
            return None
        candidates = [u["user_id"] for u in users if u.get("user_id")]
        open_tasks = task_repo.list_tasks(org_id, status="open", limit=500)
        workloads = build_workload_map(open_tasks)
        strategy = (definition or {}).get("assignment_strategy", "load_balance")
        return assign_user(
            strategy=strategy,
            candidates=candidates,
            workloads=workloads,
            counter_key=f"{org_id}:{role_name}",
            metadata=metadata,
        )

    def apply_definition_escalation_policies(self, org_id: str, instance: dict, *, trace_id: str | None = None) -> None:
        from app.modules.workflows.services.escalation_service import escalation_service

        definition = self._definition_for_instance(org_id, instance)
        metadata = instance.get("metadata") or {}
        for policy in get_escalation_policies(definition):
            when = policy.get("when")
            if when and not evaluate_condition(when, metadata):
                continue
            esc_type = str(policy.get("type") or "finance_escalation")
            escalation_service.escalate_instance(
                org_id=org_id,
                instance_id=instance["id"],
                escalation_type=esc_type,
                trace_id=trace_id,
            )

    def start_approval_chain(
        self,
        *,
        org_id: str,
        instance: dict,
        step: dict,
        definition: dict | None = None,
        trace_id: str | None = None,
    ) -> dict:
        definition = definition or self._definition_for_instance(org_id, instance)
        metadata = instance.get("metadata") or {}
        chain = inject_conditional_approvers(build_approval_chain(definition, metadata), definition, metadata)
        if not chain:
            chain = [{"level": 1, "role": "finance_manager"}]
        first = chain[0]
        assignee = self.resolve_assignee_for_role(
            org_id, str(first["role"]), instance_id=instance["id"], definition=definition, metadata=metadata
        )
        with workflow_uow(org_id) as uow:
            approval = uow.insert_approval(
                instance_id=instance["id"],
                step_id=step["id"],
                requested_from=assignee,
                level=int(first["level"]),
            )
            uow.update_instance(
                instance["id"],
                status=apply_transition(instance.get("status") or "running", "waiting_approval"),
                current_step_id=step["id"],
                metadata={**metadata, "approval_chain": chain, "approval_level": int(first["level"])},
            )
        task_repo.create_task(
            org_id=org_id,
            workflow_instance_id=instance["id"],
            workflow_step_id=step["id"],
            task_type="approval",
            assigned_to=assignee,
            payload={"approval_id": approval["id"], "level": first["level"], "role": first["role"]},
        )
        from app.modules.platform.notifications.services.recipient_resolver import resolve_user_contact

        contact = resolve_user_contact(org_id, assignee)
        workflow_events.emit_approval_requested(
            org_id,
            approval["id"],
            instance["id"],
            trace_id=trace_id,
            approver_user_id=assignee,
            approver_email=contact.get("email"),
            entity_label=str(metadata.get("entity_label") or instance.get("workflow_type") or instance["id"]),
            amount=str(metadata.get("amount", "")) if metadata.get("amount") is not None else None,
        )
        self._publish_realtime(org_id, "approval.requested", {"approval_id": approval["id"]})
        return approval

    def advance_after_approval(
        self,
        *,
        org_id: str,
        instance: dict,
        decided_level: int,
        trace_id: str | None = None,
    ) -> dict:
        definition = self._definition_for_instance(org_id, instance)
        metadata = dict(instance.get("metadata") or {})
        chain = metadata.get("approval_chain") or inject_conditional_approvers(
            build_approval_chain(definition, metadata), definition, metadata
        )
        next_levels = [row for row in chain if int(row.get("level") or 0) > decided_level]
        if next_levels:
            nxt = next_levels[0]
            step_id = instance.get("current_step_id")
            if not step_id:
                steps = step_repo.list_steps(org_id, instance["id"])
                step_id = steps[0]["id"] if steps else None
            if step_id:
                assignee = self.resolve_assignee_for_role(
                    org_id, str(nxt["role"]), instance_id=instance["id"], definition=definition, metadata=metadata
                )
                with workflow_uow(org_id) as uow:
                    approval = uow.insert_approval(
                        instance_id=instance["id"],
                        step_id=step_id,
                        requested_from=assignee,
                        level=int(nxt["level"]),
                    )
                    uow.update_instance(
                        instance["id"],
                        status="waiting_approval",
                        metadata={**metadata, "approval_level": int(nxt["level"])},
                    )
                task_repo.create_task(
                    org_id=org_id,
                    workflow_instance_id=instance["id"],
                    workflow_step_id=step_id,
                    task_type="approval",
                    assigned_to=assignee,
                    payload={"approval_id": approval["id"], "level": nxt["level"]},
                )
                from app.modules.platform.notifications.services.recipient_resolver import resolve_user_contact

                contact = resolve_user_contact(org_id, assignee)
                workflow_events.emit_approval_requested(
                    org_id,
                    approval["id"],
                    instance["id"],
                    trace_id=trace_id,
                    approver_user_id=assignee,
                    approver_email=contact.get("email"),
                    entity_label=str(metadata.get("entity_label") or instance.get("workflow_type") or instance["id"]),
                    amount=str(metadata.get("amount", "")) if metadata.get("amount") is not None else None,
                )
                return {"status": "waiting_approval", "next_level": nxt["level"]}
        return self.continue_from_executing(org_id=org_id, instance_id=instance["id"], trace_id=trace_id)

    def continue_from_executing(self, *, org_id: str, instance_id: str, trace_id: str | None = None) -> dict:
        with workflow_span("workflow.continue", instance_id=instance_id):
            instance = workflow_repo.get_instance(org_id, instance_id)
            if not instance:
                raise ValueError("Workflow instance not found")
            definition = self._definition_for_instance(org_id, instance)
            metadata = instance.get("metadata") or {}

            with workflow_uow(org_id) as uow:
                executing = apply_transition(instance.get("status") or "approved", "executing")
                uow.update_instance(instance_id, status=executing)
            record_transition()

            steps = step_repo.list_steps(org_id, instance_id)
            plan = build_execution_plan(definition, metadata)
            plan_by_key = {s["key"]: s for s in plan.get("steps", [])}

            for step in steps:
                if step.get("status") in {"completed", "skipped", "cancelled"}:
                    continue
                step_def = plan_by_key.get(step.get("step_key"), {})
                if not step_should_run(step_def, metadata):
                    step_repo.update_step_status(org_id, step["id"], "skipped", completed=True)
                    continue
                stype = step.get("step_type")
                if stype in {"human_approval", "manager_approval"}:
                    if step.get("status") == "pending":
                        pending = approval_repo.list_pending(org_id, limit=50)
                        if any(p.get("workflow_instance_id") == instance_id for p in pending):
                            return {"status": "waiting_approval"}
                        return self.start_approval_chain(
                            org_id=org_id,
                            instance={**instance, "status": executing},
                            step=step,
                            definition=definition,
                            trace_id=trace_id,
                        )
                    continue

                result = execute_step(org_id=org_id, instance=instance, step=step, trace_id=trace_id)
                if result.get("status") in {"waiting", "waiting_ai"}:
                    step_repo.update_step_status(org_id, step["id"], "waiting_ai" if result["status"] == "waiting_ai" else "pending")
                    if result.get("status") == "waiting":
                        return self.start_approval_chain(
                            org_id=org_id, instance=instance, step=step, definition=definition, trace_id=trace_id
                        )
                    return {"status": "waiting_ai", "step_id": step["id"]}
                if result.get("status") == "failed" and result.get("retryable"):
                    return self._schedule_retry(org_id, instance, step, trace_id, definition, plan_by_key.get(step.get("step_key"), {}))
                step_repo.update_step_status(org_id, step["id"], "completed", completed=True)

            self.apply_definition_escalation_policies(org_id, instance, trace_id=trace_id)
            return self._complete_instance(org_id, instance_id, trace_id=trace_id)

    def _schedule_retry(
        self,
        org_id: str,
        instance: dict,
        step: dict,
        trace_id: str | None,
        definition: dict | None = None,
        step_def: dict | None = None,
    ) -> dict:
        from app.modules.workflows.services.retry_service import retry_delay_seconds, should_retry
        from app.modules.workflows.repositories.step_failure_repository import step_failure_repo

        policy = retry_policy_for_step(step_def or {}, definition)
        retry_count = int(step.get("retry_count") or 0) + 1
        if not should_retry(retry_count, policy):
            step_failure_repo.record_failure(
                org_id=org_id,
                instance_id=instance["id"],
                step_id=step["id"],
                error_code="max_retries_exceeded",
                error_detail="Step exceeded retry policy",
                retry_count=retry_count,
            )
            return self.fail_instance(org_id, instance["id"], "max_retries_exceeded", trace_id=trace_id)
        step_repo.update_step_status(org_id, step["id"], "failed", retry_count=retry_count)
        delay = retry_delay_seconds(retry_count, policy)
        event_bus = __import__("app.services.event_bus", fromlist=["event_bus"]).event_bus
        event_bus.publish(
            event_type="workflow.retry.scheduled",
            org_id=org_id,
            source="workflow.executor",
            trace_id=trace_id,
            payload={
                "workflow_instance_id": instance["id"],
                "step_id": step["id"],
                "retry_count": retry_count,
                "delay_seconds": delay,
            },
        )
        from app.modules.workflows.services.workflow_observability import record_retry

        record_retry()
        return {"status": "failed", "retry_count": retry_count, "delay_seconds": delay}

    def fail_instance(self, org_id: str, instance_id: str, reason: str, trace_id: str | None = None) -> dict:
        with workflow_uow(org_id) as uow:
            uow.update_instance(instance_id, status="failed")
        workflow_events.emit_workflow_failed(org_id, instance_id, reason, trace_id=trace_id)
        return {"status": "failed", "reason": reason}

    def _complete_instance(self, org_id: str, instance_id: str, trace_id: str | None = None) -> dict:
        instance = workflow_repo.get_instance(org_id, instance_id) or {}
        from app.modules.workflows.services.workflow_observability import record_workflow_latency

        started = instance.get("started_at")
        if started:
            from datetime import datetime, timezone

            delta = datetime.now(timezone.utc) - started
            record_workflow_latency(org_id, instance_id, int(delta.total_seconds() * 1000))
        with workflow_uow(org_id) as uow:
            uow.update_instance(
                instance_id,
                status=apply_transition("executing", "completed"),
                completed=True,
            )
        workflow_events.emit_workflow_completed(org_id, instance_id, trace_id=trace_id)
        self._publish_realtime(org_id, "workflow.completed", {"workflow_instance_id": instance_id})
        record_transition()
        return {"status": "completed"}

    def run_from_step(self, *, org_id: str, instance_id: str, trace_id: str | None = None) -> dict:
        instance = workflow_repo.get_instance(org_id, instance_id)
        if not instance:
            raise ValueError("Workflow instance not found")
        if instance.get("status") in TERMINAL_STATUSES:
            return {"status": instance["status"]}
        return self.continue_from_executing(org_id=org_id, instance_id=instance_id, trace_id=trace_id)


workflow_orchestrator = WorkflowOrchestrator()
