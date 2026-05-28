from __future__ import annotations

from typing import Any

from app.modules.workflows.repositories import step_repo, workflow_repo
from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator


class StepService:
    def complete_step(
        self,
        *,
        org_id: str,
        step_id: str,
        actor_id: str,
        result: str = "completed",
        output: dict | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        step = None
        instance_id = None
        for inst in workflow_repo.list_instances(org_id, limit=500):
            for s in step_repo.list_steps(org_id, inst["id"]):
                if s["id"] == step_id:
                    step = s
                    instance_id = inst["id"]
                    break
            if step:
                break
        if not step or not instance_id:
            raise ValueError("Workflow step not found")
        if step.get("status") in {"completed", "skipped", "cancelled"}:
            raise ValueError("Step already completed")
        normalized = result.strip().lower()
        if normalized in {"failed", "fail"}:
            step_repo.update_step_status(org_id, step_id, "failed", retry_count=int(step.get("retry_count") or 0) + 1)
            instance = workflow_repo.get_instance(org_id, instance_id) or {}
            definition = workflow_orchestrator._definition_for_instance(org_id, instance)
            return workflow_orchestrator._schedule_retry(org_id, instance, step, trace_id, definition, {})
        metadata = (step.get("metadata") or {}) if isinstance(step.get("metadata"), dict) else {}
        if output:
            metadata = {**metadata, "completion_output": output}
        step_repo.update_step_status(org_id, step_id, "completed", completed=True)
        return workflow_orchestrator.run_from_step(org_id=org_id, instance_id=instance_id, trace_id=trace_id)


step_service = StepService()
