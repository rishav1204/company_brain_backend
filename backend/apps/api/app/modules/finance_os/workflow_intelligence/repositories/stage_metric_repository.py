from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class StageMetricRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        metric_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.workflow_stage_metrics (
                        id, org_id, workflow_instance_id, stage_name, step_key, step_type,
                        assignee_id, entered_at, exited_at, duration_seconds,
                        queue_seconds, approval_seconds, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::uuid,
                        %s::timestamptz, %s::timestamptz, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, workflow_instance_id::text AS workflow_instance_id,
                              stage_name, step_key, duration_seconds
                    """,
                    (
                        metric_id,
                        org_id,
                        data["workflow_instance_id"],
                        data["stage_name"],
                        data.get("step_key"),
                        data.get("step_type"),
                        data.get("assignee_id"),
                        data.get("entered_at"),
                        data.get("exited_at"),
                        data.get("duration_seconds", 0),
                        data.get("queue_seconds", 0),
                        data.get("approval_seconds", 0),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_for_instance(self, org_id: str, workflow_instance_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, stage_name, step_key, step_type, assignee_id::text AS assignee_id,
                           duration_seconds, queue_seconds, approval_seconds,
                           entered_at::text AS entered_at, exited_at::text AS exited_at
                    FROM finance_os.workflow_stage_metrics
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY entered_at ASC NULLS LAST
                    """,
                    (org_id, workflow_instance_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def aggregate_by_step(self, org_id: str, *, workflow_type: str | None = None, days: int = 30) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if workflow_type:
                    cur.execute(
                        """
                        SELECT m.step_key, m.stage_name,
                               AVG(m.duration_seconds)::float8 AS avg_seconds,
                               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY m.duration_seconds)::float8 AS p95_seconds,
                               COUNT(*)::int AS sample_count
                        FROM finance_os.workflow_stage_metrics m
                        JOIN finance_os.workflow_snapshots s ON s.workflow_instance_id = m.workflow_instance_id
                          AND s.org_id = m.org_id
                        WHERE m.org_id = %s::uuid AND s.workflow_type = %s
                          AND m.created_at >= NOW() - (%s || ' days')::interval
                        GROUP BY m.step_key, m.stage_name
                        ORDER BY p95_seconds DESC NULLS LAST
                        """,
                        (org_id, workflow_type, days),
                    )
                else:
                    cur.execute(
                        """
                        SELECT step_key, stage_name,
                               AVG(duration_seconds)::float8 AS avg_seconds,
                               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_seconds)::float8 AS p95_seconds,
                               COUNT(*)::int AS sample_count
                        FROM finance_os.workflow_stage_metrics
                        WHERE org_id = %s::uuid
                          AND created_at >= NOW() - (%s || ' days')::interval
                        GROUP BY step_key, stage_name
                        ORDER BY p95_seconds DESC NULLS LAST
                        """,
                        (org_id, days),
                    )
                return [dict(r) for r in cur.fetchall()]


stage_metric_repository = StageMetricRepository()
