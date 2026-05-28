from __future__ import annotations

from app.modules.workflows.engine.execution_planner import build_execution_plan
from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.engine.workflow_compiler import resolve_threshold_role
from app.modules.workflows.engine.branch_resolver import resolve_execution_path
from app.modules.workflows.repositories import step_repo, workflow_repo
from app.modules.workflows.services.approval_service import approval_service
from app.modules.workflows.services.sla_service import compute_sla_due_at


class WorkflowRuntime:
    def bootstrap_steps(self, *, org_id: str, instance: dict, definition: dict | None) -> list[dict]:
        metadata = instance.get("metadata") or {}
        plan_steps = resolve_execution_path(definition, metadata) or build_execution_plan(definition, metadata).get("steps", [])
        created: list[dict] = []
        amount = metadata.get("amount")
        threshold_role = resolve_threshold_role(definition, float(amount) if amount is not None else None)
        for step_def in plan_steps:
            sla_hours = step_def.get("sla_hours")
            due_at = (
                compute_sla_due_at(created_at=instance.get("started_at"), sla_hours=sla_hours, org_id=org_id)
                if sla_hours
                else None
            )
            step = step_repo.create_step(
                org_id=org_id,
                workflow_instance_id=instance["id"],
                step_key=step_def["key"],
                step_type=step_def["type"],
                due_at=due_at,
                metadata={"threshold_role": threshold_role} if threshold_role else {},
            )
            created.append(step)
        if created:
            workflow_repo.update_instance_status(
                org_id,
                instance["id"],
                apply_transition(current_status=instance.get("status") or "queued", target_status="running"),
                current_step_id=created[0]["id"],
            )
        return created

    def advance_human_step(self, *, org_id: str, instance_id: str, step: dict, assignee: str | None, trace_id: str | None) -> dict:
        return approval_service.request_approval(
            org_id=org_id,
            instance_id=instance_id,
            step_id=step["id"],
            requested_from=assignee,
            trace_id=trace_id,
        )


workflow_runtime = WorkflowRuntime()
