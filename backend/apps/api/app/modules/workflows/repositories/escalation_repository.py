from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class EscalationRepository:
    def create_escalation(
        self,
        *,
        org_id: str,
        workflow_instance_id: str,
        escalation_type: str,
        escalated_to: str | None,
        step_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        esc_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.escalations (
                        id, org_id, workflow_instance_id, step_id, escalation_type, escalated_to, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s::jsonb)
                    RETURNING id::text AS id, escalation_type, triggered_at
                    """,
                    (esc_id, org_id, workflow_instance_id, step_id, escalation_type, escalated_to, Json(metadata or {})),
                )
                return cur.fetchone()

    def list_escalations(self, org_id: str, *, unresolved_only: bool = True, limit: int = 100) -> list[dict[str, Any]]:
        clause = "AND resolved_at IS NULL" if unresolved_only else ""
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT e.id::text AS id, e.escalation_type, e.escalated_to::text AS escalated_to,
                           e.triggered_at, i.workflow_type, i.id::text AS workflow_instance_id
                    FROM workflow.escalations e
                    JOIN workflow.workflow_instances i ON i.id = e.workflow_instance_id
                    WHERE e.org_id = %s::uuid {clause}
                    ORDER BY e.triggered_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def resolve(self, org_id: str, escalation_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.escalations SET resolved_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id
                    """,
                    (escalation_id, org_id),
                )
                return cur.fetchone() is not None
