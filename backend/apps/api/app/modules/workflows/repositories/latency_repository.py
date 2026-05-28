from __future__ import annotations

from typing import Any

from app.services.db import get_db_conn, set_rls_org


class LatencyRepository:
    def record_sample(
        self,
        *,
        org_id: str,
        metric_type: str,
        duration_ms: int,
        workflow_instance_id: str | None = None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.latency_samples (org_id, workflow_instance_id, metric_type, duration_ms)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    """,
                    (org_id, workflow_instance_id, metric_type, duration_ms),
                )

    def aggregate(self, org_id: str, *, metric_type: str, limit: int = 500) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS sample_count,
                        COALESCE(AVG(duration_ms), 0)::int AS avg_ms,
                        COALESCE(MAX(duration_ms), 0)::int AS max_ms,
                        COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms), 0)::int AS p95_ms
                    FROM (
                        SELECT duration_ms
                        FROM workflow.latency_samples
                        WHERE org_id = %s::uuid AND metric_type = %s
                        ORDER BY recorded_at DESC
                        LIMIT %s
                    ) recent
                    """,
                    (org_id, metric_type, limit),
                )
                row = cur.fetchone() or {}
        return {
            "metric_type": metric_type,
            "sample_count": int(row.get("sample_count") or 0),
            "avg_ms": int(row.get("avg_ms") or 0),
            "max_ms": int(row.get("max_ms") or 0),
            "p95_ms": int(row.get("p95_ms") or 0),
        }


latency_repo = LatencyRepository()
