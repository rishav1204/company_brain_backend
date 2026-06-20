from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.finance_os.workflow_intelligence.engine.workflow_graph_engine import build_execution_graph
from app.modules.finance_os.workflow_intelligence.engine.workflow_scoring_engine import efficiency_score
from app.modules.finance_os.workflow_intelligence.repositories.snapshot_repository import snapshot_repository
from app.modules.finance_os.workflow_intelligence.repositories.stage_metric_repository import stage_metric_repository
from app.modules.workflows.repositories import step_repo, workflow_repo


class WorkflowAnalysisService:
    def ingest_instance(self, org_id: str, *, workflow_instance_id: str) -> dict:
        instance = workflow_repo.get_instance(org_id, workflow_instance_id)
        if not instance:
            raise ValueError("Workflow instance not found")

        definition = workflow_repo.get_definition_by_key(org_id, str(instance.get("workflow_type") or "")) or {}
        def_json = definition.get("definition_json") if isinstance(definition.get("definition_json"), dict) else {}
        def_steps = def_json.get("steps") or []

        steps = step_repo.list_steps(org_id, workflow_instance_id)
        graph = build_execution_graph(definition_steps=def_steps, executed_steps=steps)

        started = instance.get("started_at")
        completed = instance.get("completed_at")
        duration = 0
        if started and completed:
            try:
                t0 = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
                duration = max(0, int((t1 - t0).total_seconds()))
            except ValueError:
                duration = 0

        eff = efficiency_score(actual_seconds=float(duration or 1), sla_target_seconds=None, historical_p50=None)

        snap = snapshot_repository.upsert(
            org_id,
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_definition_id": instance.get("workflow_definition_id"),
                "workflow_type": str(instance.get("workflow_type") or "unknown"),
                "entity_type": instance.get("entity_type"),
                "entity_id": instance.get("entity_id"),
                "started_at": started,
                "completed_at": completed,
                "duration_seconds": duration,
                "status": str(instance.get("status") or "running"),
                "efficiency_score": eff,
                "metadata": {"graph": graph},
            },
        )

        for node in graph:
            if not node.get("exited_at") and node.get("status") not in {"completed", "skipped"}:
                continue
            stage_metric_repository.create(
                org_id,
                data={
                    "workflow_instance_id": workflow_instance_id,
                    "stage_name": node.get("stage_name") or node.get("step_key"),
                    "step_key": node.get("step_key"),
                    "step_type": node.get("step_type"),
                    "assignee_id": node.get("assignee_id"),
                    "entered_at": node.get("entered_at"),
                    "exited_at": node.get("exited_at"),
                    "duration_seconds": node.get("duration_seconds", 0),
                },
            )

        return {"snapshot": snap, "graph": graph}

    def get_snapshot(self, org_id: str, workflow_instance_id: str) -> dict | None:
        return snapshot_repository.get_by_instance(org_id, workflow_instance_id)


workflow_analysis_service = WorkflowAnalysisService()
