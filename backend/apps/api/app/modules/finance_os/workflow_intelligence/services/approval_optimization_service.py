from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.ai.optimization_advisor import generate_recommendations
from app.modules.finance_os.workflow_intelligence.engine.optimization_engine import detect_queue_overload
from app.modules.finance_os.workflow_intelligence.repositories.recommendation_repository import recommendation_repository
from app.modules.finance_os.workflow_intelligence.repositories.stage_metric_repository import stage_metric_repository
from app.modules.finance_os.workflow_intelligence.retrieval.approval_patterns import approval_pass_through_rates, rejection_rates
from app.services.db import get_db_conn, set_rls_org


class ApprovalOptimizationService:
    def _pending_by_assignee(self, org_id: str) -> dict[str, int]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT requested_from_user_id::text AS uid, COUNT(*)::int AS cnt
                    FROM workflow.approvals
                    WHERE org_id = %s::uuid AND decision = 'pending'
                      AND requested_from_user_id IS NOT NULL
                    GROUP BY requested_from_user_id
                    """,
                    (org_id,),
                )
                return {str(r["uid"]): int(r["cnt"]) for r in cur.fetchall()}

    def generate(self, org_id: str, *, workflow_type: str, workflow_instance_id: str | None = None) -> list[dict]:
        stats = stage_metric_repository.aggregate_by_step(org_id, workflow_type=workflow_type)
        ptr = approval_pass_through_rates(org_id, workflow_type=workflow_type)
        rej = rejection_rates(org_id, workflow_type=workflow_type)
        pending = self._pending_by_assignee(org_id)
        raw = generate_recommendations(
            stage_stats=stats,
            pass_through_by_stage=ptr,
            rejection_by_stage=rej,
            pending_by_assignee=pending,
        )
        saved: list[dict] = []
        for r in raw:
            saved.append(
                recommendation_repository.create(
                    org_id,
                    data={
                        "workflow_type": workflow_type,
                        "workflow_instance_id": workflow_instance_id,
                        "recommendation_type": r["recommendation_type"],
                        "recommendation": r["recommendation"],
                        "impact_score": r.get("impact_score", 0),
                        "metadata": r.get("metadata") or {},
                    },
                )
            )
        return saved

    def accept(self, org_id: str, *, recommendation_id: str, user_id: str) -> dict | None:
        return recommendation_repository.update_status(
            org_id, recommendation_id, status="accepted", accepted_by=user_id
        )

    def reject(self, org_id: str, *, recommendation_id: str, user_id: str) -> dict | None:
        return recommendation_repository.update_status(
            org_id, recommendation_id, status="rejected", accepted_by=user_id
        )

    def list_open(self, org_id: str, *, workflow_type: str | None = None) -> list[dict]:
        return recommendation_repository.list_open(org_id, workflow_type=workflow_type)

    def queue_overload(self, org_id: str) -> list[dict]:
        return detect_queue_overload(self._pending_by_assignee(org_id))


approval_optimization_service = ApprovalOptimizationService()
