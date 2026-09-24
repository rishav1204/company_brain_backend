from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ApprovalRepository:
    def create_approval(
        self,
        *,
        org_id: str,
        workflow_instance_id: str,
        workflow_step_id: str,
        requested_from_user_id: str | None,
        level: int = 1,
        amount_threshold: float | None = None,
    ) -> dict[str, Any]:
        approval_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.approvals (
                        id, org_id, workflow_instance_id, workflow_step_id,
                        requested_from_user_id, decision, level, amount_threshold
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'pending', %s, %s)
                    RETURNING id::text AS id, decision, level, created_at
                    """,
                    (approval_id, org_id, workflow_instance_id, workflow_step_id, requested_from_user_id, level, amount_threshold),
                )
                return cur.fetchone()

    def decide(
        self,
        *,
        org_id: str,
        approval_id: str,
        approver_user_id: str,
        decision: str,
        decision_reason: str | None = None,
    ) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.approvals
                    SET approver_user_id = %s::uuid, decision = %s, decision_reason = %s, decided_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid AND decision = 'pending'
                    RETURNING id::text AS id, workflow_instance_id::text AS workflow_instance_id,
                              workflow_step_id::text AS workflow_step_id, decision
                    """,
                    (approver_user_id, decision, decision_reason, approval_id, org_id),
                )
                return cur.fetchone()

    def list_pending(self, org_id: str, *, approver_user_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.id::text AS id, a.workflow_instance_id::text AS workflow_instance_id,
                           a.workflow_step_id::text AS workflow_step_id, a.level, a.created_at,
                           i.workflow_type, i.metadata, i.started_by::text AS owner_user_id
                    FROM workflow.approvals a
                    JOIN workflow.workflow_instances i ON i.id = a.workflow_instance_id
                    WHERE a.org_id = %s::uuid AND a.decision = 'pending'
                    ORDER BY a.created_at ASC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def get_approval(self, org_id: str, approval_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, workflow_instance_id::text AS workflow_instance_id,
                           workflow_step_id::text AS workflow_step_id, approver_user_id::text AS approver_user_id,
                           requested_from_user_id::text AS requested_from_user_id, decision, decision_reason
                    FROM workflow.approvals
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, approval_id),
                )
                return cur.fetchone()

    def list_for_instance(self, org_id: str, workflow_instance_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, workflow_instance_id::text AS workflow_instance_id,
                           workflow_step_id::text AS workflow_step_id,
                           approver_user_id::text AS approver_user_id,
                           requested_from_user_id::text AS requested_from_user_id,
                           decision, decision_reason, level, amount_threshold,
                           created_at, decided_at
                    FROM workflow.approvals
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY level ASC, created_at ASC
                    LIMIT %s
                    """,
                    (org_id, workflow_instance_id, limit),
                )
                return list(cur.fetchall())
