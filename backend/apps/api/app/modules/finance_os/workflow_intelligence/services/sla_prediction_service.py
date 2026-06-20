from __future__ import annotations

from datetime import datetime

from app.modules.finance_os.workflow_intelligence.ai.sla_predictor import predict_sla
from app.modules.finance_os.workflow_intelligence.engine.workflow_graph_engine import remaining_stages
from app.modules.finance_os.workflow_intelligence.repositories.prediction_repository import prediction_repository
from app.modules.finance_os.workflow_intelligence.retrieval.historical_slas import historical_stage_p95
from app.modules.workflows.repositories import step_repo, workflow_repo
from app.services.db import get_db_conn, set_rls_org


class SlaPredictionService:
    def _pending_for_assignee(self, org_id: str, assignee_id: str | None) -> int:
        if not assignee_id:
            return 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt FROM workflow.approvals
                    WHERE org_id = %s::uuid AND decision = 'pending'
                      AND requested_from_user_id = %s::uuid
                    """,
                    (org_id, assignee_id),
                )
                row = cur.fetchone()
                return int(row["cnt"]) if row else 0

    def predict_for_instance(self, org_id: str, *, workflow_instance_id: str) -> dict:
        instance = workflow_repo.get_instance(org_id, workflow_instance_id)
        if not instance:
            raise ValueError("Workflow instance not found")
        wf_type = str(instance.get("workflow_type") or "")
        hist = historical_stage_p95(org_id, workflow_type=wf_type)
        steps = step_repo.list_steps(org_id, workflow_instance_id)
        graph = [{"step_key": s.get("step_key"), "status": s.get("status")} for s in steps]
        remaining = remaining_stages(graph)
        remaining_p95 = [hist.get(str(n.get("step_key") or ""), 3600) for n in remaining]

        current_step = next((s for s in steps if s.get("status") in {"pending", "waiting_approval"}), None)
        assignee = current_step.get("assigned_to") if current_step else None
        pending = self._pending_for_assignee(org_id, assignee)

        due_at = None
        if current_step and current_step.get("due_at"):
            try:
                due_at = datetime.fromisoformat(str(current_step["due_at"]).replace("Z", "+00:00"))
            except ValueError:
                due_at = None

        result = predict_sla(
            {
                "remaining_stage_p95": remaining_p95,
                "pending_approvals": pending,
                "avg_approval_wait_seconds": 3600,
                "due_at": due_at,
            }
        )

        pred = prediction_repository.create(
            org_id,
            data={
                "workflow_instance_id": workflow_instance_id,
                "prediction_type": "sla_breach_risk",
                "predicted_value": result["breach_risk"],
                "confidence_score": result["confidence_score"],
                "metadata": result,
            },
        )
        prediction_repository.create(
            org_id,
            data={
                "workflow_instance_id": workflow_instance_id,
                "prediction_type": "sla_completion",
                "predicted_value": result["predicted_eta"],
                "confidence_score": result["confidence_score"],
                "metadata": result,
            },
        )
        return {**result, "prediction_id": pred.get("id")}

    def list_risks(self, org_id: str, *, limit: int = 50) -> list[dict]:
        return prediction_repository.list_sla_risks(org_id, limit=limit)


sla_prediction_service = SlaPredictionService()
