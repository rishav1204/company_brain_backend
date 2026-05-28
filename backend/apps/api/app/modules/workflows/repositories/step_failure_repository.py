from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class StepFailureRepository:
    def record_failure(
        self,
        *,
        org_id: str,
        instance_id: str,
        step_id: str,
        error_code: str,
        error_detail: str | None = None,
        retry_count: int = 0,
        payload: dict | None = None,
    ) -> dict:
        failure_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.step_failures (
                        id, org_id, workflow_instance_id, workflow_step_id,
                        error_code, error_detail, retry_count, payload
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                    RETURNING id::text AS id, created_at
                    """,
                    (
                        failure_id,
                        org_id,
                        instance_id,
                        step_id,
                        error_code,
                        error_detail,
                        retry_count,
                        Json(payload or {}),
                    ),
                )
                row = cur.fetchone()
        from app.services.metrics import metrics_store

        metrics_store.incr_queue_dlq()
        return row or {"id": failure_id}

    def list_open(self, org_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, workflow_instance_id::text AS workflow_instance_id,
                           workflow_step_id::text AS workflow_step_id, error_code, retry_count, created_at
                    FROM workflow.step_failures
                    WHERE org_id = %s::uuid AND resolved_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return cur.fetchall() or []


step_failure_repo = StepFailureRepository()
