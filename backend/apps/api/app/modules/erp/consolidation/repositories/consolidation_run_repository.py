from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ConsolidationRunRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='erp' AND table_name='consolidation_runs' LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(
        self,
        org_id: str,
        *,
        group_company_id: str,
        fiscal_period_id: str,
        company_ids: list[str],
        started_by: str | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.consolidation_runs (
                        id, org_id, group_company_id, fiscal_period_id,
                        status, company_ids, started_by
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'running', %s::jsonb, %s::uuid)
                    RETURNING id::text, status, started_at
                    """,
                    (row_id, org_id, group_company_id, fiscal_period_id, Json(company_ids), started_by),
                )
                row = cur.fetchone()
                conn.commit()
                return {"id": row[0], "status": row[1], "started_at": row[2]}

    def update_status(
        self,
        org_id: str,
        run_id: str,
        *,
        status: str,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.consolidation_runs
                    SET status = %s,
                        error_message = COALESCE(%s, error_message),
                        metadata = COALESCE(%s::jsonb, metadata),
                        completed_at = CASE WHEN %s IN ('completed', 'failed') THEN now() ELSE completed_at END
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, error_message, Json(metadata) if metadata else None, status, org_id, run_id),
                )
                conn.commit()

    def get(self, org_id: str, run_id: str) -> dict[str, Any] | None:
        if not self.schema_ready():
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, group_company_id::text, fiscal_period_id::text,
                           status, company_ids, started_by::text, error_message,
                           metadata, started_at, completed_at
                    FROM erp.consolidation_runs
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    def list_runs(self, org_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, group_company_id::text, fiscal_period_id::text,
                           status, started_at, completed_at
                    FROM erp.consolidation_runs
                    WHERE org_id = %s::uuid
                    ORDER BY started_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


consolidation_run_repository = ConsolidationRunRepository()
