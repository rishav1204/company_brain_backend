from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ReportRunsRepository:
    def create(
        self,
        org_id: str,
        *,
        report_type: str,
        filters: dict | None = None,
        created_by: str | None = None,
    ) -> dict:
        run_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp_reporting.report_runs (
                      id, org_id, report_type, status, filters, created_by
                    )
                    VALUES (%s::uuid, %s::uuid, %s, 'queued', %s::jsonb, %s::uuid)
                    RETURNING id::text, report_type, status, filters, created_at::text
                    """,
                    (run_id, org_id, report_type, Json(filters or {}), created_by),
                )
                return dict(cur.fetchone() or {"id": run_id})

    def get(self, org_id: str, *, run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, report_type, status, filters, file_ref, error_message,
                           created_at::text, completed_at::text
                    FROM erp_reporting.report_runs
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def mark_completed(self, org_id: str, *, run_id: str, file_ref: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp_reporting.report_runs
                    SET status = 'completed', file_ref = %s, completed_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, file_ref
                    """,
                    (file_ref, org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def mark_failed(self, org_id: str, *, run_id: str, error_message: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp_reporting.report_runs
                    SET status = 'failed', error_message = %s, completed_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, error_message
                    """,
                    (error_message[:2000], org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def delete_older_than(self, org_id: str, *, days: int = 90) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM erp_reporting.report_runs
                    WHERE org_id = %s::uuid
                      AND created_at < now() - make_interval(days => %s)
                      AND status IN ('completed', 'failed')
                    """,
                    (org_id, int(days)),
                )
                return int(cur.rowcount or 0)


report_runs_repository = ReportRunsRepository()
