from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class WorkflowTaskRepository:
    def create_task(
        self,
        *,
        org_id: str,
        workflow_instance_id: str,
        task_type: str,
        assigned_to: str | None = None,
        workflow_step_id: str | None = None,
        due_at: Any = None,
        payload: dict | None = None,
    ) -> dict[str, Any]:
        task_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.workflow_tasks (
                        id, org_id, workflow_instance_id, workflow_step_id,
                        task_type, assigned_to, status, due_at, payload
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, 'open', %s, %s::jsonb)
                    RETURNING id::text AS id, task_type, status, assigned_to::text AS assigned_to, due_at
                    """,
                    (task_id, org_id, workflow_instance_id, workflow_step_id, task_type, assigned_to, due_at, Json(payload or {})),
                )
                return cur.fetchone()

    def list_tasks(
        self,
        org_id: str,
        *,
        assigned_to: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        clauses = ["t.org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if assigned_to:
            clauses.append("t.assigned_to = %s::uuid")
            params.append(assigned_to)
        if status:
            clauses.append("t.status = %s")
            params.append(status)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT t.id::text AS id, t.task_type, t.status, t.assigned_to::text AS assigned_to,
                           t.due_at, t.payload, i.workflow_type, i.id::text AS workflow_instance_id
                    FROM workflow.workflow_tasks t
                    JOIN workflow.workflow_instances i ON i.id = t.workflow_instance_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY t.due_at ASC NULLS LAST, t.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return list(cur.fetchall())

    def complete_task(self, org_id: str, task_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.workflow_tasks
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id
                    """,
                    (task_id, org_id),
                )
                return cur.fetchone() is not None

    def assign_task(self, org_id: str, task_id: str, assigned_to: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.workflow_tasks SET assigned_to = %s::uuid
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, assigned_to::text AS assigned_to, status
                    """,
                    (assigned_to, task_id, org_id),
                )
                return cur.fetchone()
