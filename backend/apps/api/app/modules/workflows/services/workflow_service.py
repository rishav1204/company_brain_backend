from __future__ import annotations

from typing import Any

from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.engine.workflow_state_machine import legacy_state_to_status, status_to_legacy_state
from app.modules.workflows.events.workflow_events import emit_workflow_created
from app.modules.workflows.repositories import step_repo, workflow_repo
from app.modules.workflows.services.workflow_executor import workflow_executor
from app.services.repositories import workflows_repo


class WorkflowService:
    def schema_ready(self) -> bool:
        return workflow_repo.schema_ready()

    def resolve_instance(self, org_id: str, workflow_id: str) -> dict[str, Any] | None:
        if self.schema_ready():
            inst = workflow_repo.get_instance(org_id, workflow_id)
            if inst:
                return inst
            inst = workflow_repo.get_instance_by_legacy(org_id, workflow_id)
            if inst:
                return inst
        legacy = workflows_repo.get_workflow(org_id, workflow_id)
        if not legacy:
            return None
        return {
            "id": legacy["id"],
            "legacy_workflow_id": legacy["id"],
            "workflow_type": legacy["workflow_type"],
            "status": legacy_state_to_status(legacy.get("state", "running")),
            "started_by": legacy.get("owner_user_id"),
            "started_at": legacy.get("started_at"),
            "completed_at": legacy.get("closed_at"),
            "metadata": {},
        }

    def list_for_api(
        self,
        org_id: str,
        *,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if self.schema_ready():
            rows = workflow_repo.list_instances(org_id, workflow_type=workflow_type, status=status, limit=limit)
            return [self._to_legacy_row(r) for r in rows]
        return workflows_repo.list_workflows(org_id=org_id, workflow_type=workflow_type, status=status, limit=limit)

    def _to_legacy_row(self, row: dict) -> dict:
        api_id = row.get("legacy_workflow_id") or row["id"]
        status = row.get("status") or "running"
        return {
            "id": api_id,
            "workflow_type": row["workflow_type"],
            "state": status_to_legacy_state(status),
            "owner_user_id": row.get("owner_user_id"),
            "started_at": row.get("started_at"),
            "closed_at": row.get("completed_at"),
            "org_id": row.get("org_id"),
            "metadata": row.get("metadata") or {},
        }

    def list_timeline(self, org_id: str, workflow_id: str) -> list[dict]:
        inst = self.resolve_instance(org_id, workflow_id)
        if inst and self.schema_ready():
            return step_repo.list_timeline(org_id, inst["id"])
        return workflows_repo.list_timeline(org_id=org_id, workflow_id=workflow_id)

    def start_workflow(
        self,
        *,
        org_id: str,
        user_id: str,
        workflow_key: str | None = None,
        workflow_type: str | None = None,
        entity_type: str = "workflow",
        entity_id: str | None = None,
        metadata: dict | None = None,
        trace_id: str | None = None,
    ) -> dict:
        if not self.schema_ready():
            raise RuntimeError("Workflow engine schema not ready")
        definition = None
        definition_id = None
        wtype = workflow_type or workflow_key or "generic"
        if workflow_key:
            definition = workflow_repo.get_definition_by_key(org_id, workflow_key)
            if definition:
                definition_id = definition["id"]
                wtype = workflow_key
        started_by = user_id if str(user_id or "").strip() else None
        instance = workflow_repo.create_instance(
            org_id=org_id,
            workflow_type=wtype,
            started_by=started_by,
            definition_id=definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            status="queued",
        )
        emit_workflow_created(org_id, instance["id"], trace_id=trace_id, extra={"workflow_type": wtype})
        def_json = (definition or {}).get("definition_json") if definition else {}
        if isinstance(def_json, str):
            import json

            def_json = json.loads(def_json)
        return workflow_executor.start(
            org_id=org_id,
            instance=instance,
            definition=def_json if isinstance(def_json, dict) else {},
            trace_id=trace_id,
        )

    def transition(
        self,
        *,
        org_id: str,
        workflow_id: str,
        target_status: str,
        actor_id: str,
        trace_id: str | None = None,
    ) -> dict:
        inst = self.resolve_instance(org_id, workflow_id)
        if not inst:
            raise ValueError("Workflow not found")
        if not self.schema_ready():
            raise RuntimeError("Workflow engine schema not ready")
        instance_id = inst["id"]
        new_status = apply_transition(current_status=inst.get("status") or "running", target_status=target_status)
        completed = new_status in {"completed", "rejected", "cancelled"}
        from app.modules.workflows.engine.checkpoint_manager import save_checkpoint
        from app.modules.workflows.repositories.workflow_uow import workflow_uow
        from app.modules.workflows.services.workflow_observability import record_transition

        metadata = save_checkpoint(
            inst.get("metadata"),
            {"from": inst.get("status"), "to": new_status, "actor_id": actor_id},
        )
        with workflow_uow(org_id) as uow:
            updated = uow.update_instance(instance_id, status=new_status, metadata=metadata, completed=completed)
        record_transition()
        legacy_id = inst.get("legacy_workflow_id")
        if legacy_id:
            try:
                workflows_repo.add_timeline_step(
                    org_id=org_id,
                    workflow_id=legacy_id,
                    step_type="workflow.transition",
                    state=status_to_legacy_state(new_status),
                )
            except Exception:
                pass
        return updated or inst

    def state_counts(self, org_id: str) -> dict[str, int]:
        if self.schema_ready():
            return workflow_repo.state_counts(org_id)
        return {"total": 0, "blocked_count": 0, "pending_approval_count": 0}

    def ensure_instance_for_legacy(self, org_id: str, legacy_workflow: dict) -> dict | None:
        if not self.schema_ready():
            return None
        legacy_id = legacy_workflow["id"]
        existing = workflow_repo.get_instance_by_legacy(org_id, legacy_id)
        if existing:
            return existing
        return workflow_repo.create_instance(
            org_id=org_id,
            workflow_type=legacy_workflow["workflow_type"],
            started_by=legacy_workflow.get("owner_user_id"),
            legacy_workflow_id=legacy_id,
            entity_type="workflow",
            entity_id=legacy_id,
            status=legacy_state_to_status(legacy_workflow.get("state", "running")),
        )


workflow_service = WorkflowService()
