from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.repositories.snapshot_repository import snapshot_repository
from app.modules.finance_os.workflow_intelligence.repositories.stage_metric_repository import stage_metric_repository
from app.services.db import get_db_conn, set_rls_org


class WorkflowPatternService:
    def analytics(self, org_id: str, *, workflow_type: str | None = None, days: int = 30) -> dict:
        snapshots = snapshot_repository.list_recent(org_id, workflow_type=workflow_type, limit=200)
        stage_stats = stage_metric_repository.aggregate_by_step(org_id, workflow_type=workflow_type, days=days)
        avg_eff = 0.0
        if snapshots:
            avg_eff = sum(float(s.get("efficiency_score") or 0) for s in snapshots) / len(snapshots)

        delayed: list[dict] = []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT workflow_type, AVG(duration_seconds)::float8 AS avg_duration, COUNT(*)::int AS cnt
                    FROM finance_os.workflow_snapshots
                    WHERE org_id = %s::uuid
                      AND created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY workflow_type
                    ORDER BY avg_duration DESC
                    LIMIT 10
                    """,
                    (org_id, days),
                )
                delayed = [dict(r) for r in cur.fetchall()]

        return {
            "workflow_type": workflow_type,
            "snapshot_count": len(snapshots),
            "avg_efficiency_score": round(avg_eff, 2),
            "stage_stats": stage_stats[:20],
            "most_delayed_workflows": delayed,
        }


workflow_pattern_service = WorkflowPatternService()
