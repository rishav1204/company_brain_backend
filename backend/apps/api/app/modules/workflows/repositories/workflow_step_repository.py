from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class WorkflowStepRepository:
    def create_step(
        self,
        *,
        org_id: str,
        workflow_instance_id: str,
        step_key: str,
        step_type: str,
        assigned_to: str | None = None,
        due_at: Any = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        step_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.workflow_steps (
                        id, org_id, workflow_instance_id, step_key, step_type, status,
                        assigned_to, started_at, due_at, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', %s::uuid, NOW(), %s, %s::jsonb)
                    RETURNING id::text AS id, step_key, step_type, status, assigned_to::text AS assigned_to, due_at
                    """,
                    (step_id, org_id, workflow_instance_id, step_key, step_type, assigned_to, due_at, Json(metadata or {})),
                )
                return cur.fetchone()

    def update_step_status(
        self,
        org_id: str,
        step_id: str,
        status: str,
        *,
        completed: bool = False,
        retry_count: int | None = None,
    ) -> None:
        sets = ["status = %s"]
        params: list[Any] = [status]
        if completed:
            sets.append("completed_at = NOW()")
        if retry_count is not None:
            sets.append("retry_count = %s")
            params.append(retry_count)
        params.extend([step_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE workflow.workflow_steps SET {', '.join(sets)} WHERE id = %s::uuid AND org_id = %s::uuid",
                    tuple(params),
                )

    def list_steps(self, org_id: str, workflow_instance_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, step_key, step_type, status, retry_count,
                           assigned_to::text AS assigned_to, started_at, completed_at, due_at, metadata
                    FROM workflow.workflow_steps
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY started_at ASC NULLS LAST, created_at ASC
                    """,
                    (org_id, workflow_instance_id),
                )
                return list(cur.fetchall())

    def list_timeline(self, org_id: str, workflow_instance_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        step_type AS event_type,
                        COALESCE(started_at, created_at) AS occurred_at,
                        CONCAT('step=', step_key, ';status=', status) AS detail
                    FROM workflow.workflow_steps
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY COALESCE(started_at, created_at) ASC
                    """,
                    (org_id, workflow_instance_id),
                )
                return [dict(row) for row in cur.fetchall()]
