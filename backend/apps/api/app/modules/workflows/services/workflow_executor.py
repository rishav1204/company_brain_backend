from __future__ import annotations

from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.events.workflow_events import emit_workflow_started
from app.modules.workflows.repositories import workflow_repo
from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator
from app.modules.workflows.services.workflow_runtime import workflow_runtime


class WorkflowExecutor:
    def start(self, *, org_id: str, instance: dict, definition: dict | None, trace_id: str | None = None) -> dict:
        target = apply_transition(current_status=instance.get("status") or "draft", target_status="running")
        updated = workflow_repo.update_instance_status(org_id, instance["id"], target)
        emit_workflow_started(org_id, instance["id"], trace_id=trace_id)
        workflow_runtime.bootstrap_steps(org_id=org_id, instance={**instance, "status": target}, definition=definition)
        result = workflow_orchestrator.run_from_step(org_id=org_id, instance_id=instance["id"], trace_id=trace_id)
        return updated or {**instance, "status": result.get("status", target)}

    def complete(self, *, org_id: str, instance_id: str, actor_id: str, trace_id: str | None = None) -> dict:
        return workflow_orchestrator._complete_instance(org_id, instance_id, trace_id=trace_id)

    def fail(self, *, org_id: str, instance_id: str, reason: str, trace_id: str | None = None) -> dict:
        return workflow_orchestrator.fail_instance(org_id, instance_id, reason, trace_id=trace_id)


workflow_executor = WorkflowExecutor()
