from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class WorkflowUnitOfWork:
    def __init__(self, conn: Any, org_id: str) -> None:
        self.conn = conn
        self.org_id = org_id

    def update_instance(
        self,
        instance_id: str,
        *,
        status: str | None = None,
        current_step_id: str | None = None,
        metadata: dict | None = None,
        priority: str | None = None,
        completed: bool = False,
    ) -> dict | None:
        sets: list[str] = ["updated_at = NOW()"]
        params: list[Any] = []
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if current_step_id is not None:
            sets.append("current_step_id = %s::uuid")
            params.append(current_step_id)
        if metadata is not None:
            sets.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if priority is not None:
            sets.append("priority = %s")
            params.append(priority)
        if completed:
            sets.append("completed_at = NOW()")
        params.extend([instance_id, self.org_id])
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE workflow.workflow_instances SET {', '.join(sets)}
                WHERE id = %s::uuid AND org_id = %s::uuid
                RETURNING id::text AS id, status, metadata, priority, current_step_id::text AS current_step_id
                """,
                tuple(params),
            )
            return cur.fetchone()

    def update_step(self, step_id: str, *, status: str, completed: bool = False, retry_count: int | None = None) -> None:
        sets = ["status = %s"]
        params: list[Any] = [status]
        if completed:
            sets.append("completed_at = NOW()")
        if retry_count is not None:
            sets.append("retry_count = %s")
            params.append(retry_count)
        params.extend([step_id, self.org_id])
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE workflow.workflow_steps SET {', '.join(sets)} WHERE id = %s::uuid AND org_id = %s::uuid",
                tuple(params),
            )

    def insert_approval(
        self,
        *,
        instance_id: str,
        step_id: str,
        requested_from: str | None,
        level: int,
        amount_threshold: float | None = None,
    ) -> dict:
        approval_id = str(uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow.approvals (
                    id, org_id, workflow_instance_id, workflow_step_id,
                    requested_from_user_id, decision, level, amount_threshold
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'pending', %s, %s)
                RETURNING id::text AS id, level
                """,
                (approval_id, self.org_id, instance_id, step_id, requested_from, level, amount_threshold),
            )
            return cur.fetchone()

    def decide_approval(
        self,
        approval_id: str,
        *,
        approver_user_id: str,
        decision: str,
        reason: str | None,
    ) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow.approvals
                SET approver_user_id = %s::uuid, decision = %s, decision_reason = %s, decided_at = NOW()
                WHERE id = %s::uuid AND org_id = %s::uuid AND decision = 'pending'
                RETURNING id::text AS id, workflow_instance_id::text AS workflow_instance_id,
                          workflow_step_id::text AS workflow_step_id, level, decision
                """,
                (approver_user_id, decision, reason, approval_id, self.org_id),
            )
            return cur.fetchone()

    def pending_approval_at_level(self, instance_id: str, level: int) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, level, decision
                FROM workflow.approvals
                WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid AND level = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (self.org_id, instance_id, level),
            )
            return cur.fetchone()


@contextmanager
def workflow_uow(org_id: str) -> Iterator[WorkflowUnitOfWork]:
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        yield WorkflowUnitOfWork(conn, org_id)
