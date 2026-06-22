from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class PolicyExceptionRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'governance' AND table_name = 'policy_exceptions'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(
        self,
        org_id: str,
        *,
        policy_code: str,
        action: str,
        reason: str,
        object_type: str | None = None,
        object_id: str | None = None,
        workflow_instance_id: str | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.policy_exceptions (
                        id, org_id, policy_code, object_type, object_id, action, reason, workflow_instance_id
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, %s, %s, %s::uuid)
                    RETURNING id::text, status, policy_code
                    """,
                    (row_id, org_id, policy_code, object_type, object_id, action, reason, workflow_instance_id),
                )
                return dict(cur.fetchone() or {})

    def list_open(self, org_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, policy_code, action, reason, status, object_type, object_id::text, created_at
                    FROM governance.policy_exceptions
                    WHERE org_id = %s::uuid AND status IN ('pending', 'approved')
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


policy_exception_repository = PolicyExceptionRepository()
