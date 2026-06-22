from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PolicyDecisionRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'governance' AND table_name = 'policy_decisions'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def record(
        self,
        org_id: str,
        *,
        action: str,
        decision: str,
        object_type: str | None = None,
        object_id: str | None = None,
        policy_code: str | None = None,
        risk_level: str | None = None,
        approval_chain: list | None = None,
        input_context: dict | None = None,
        reason: str | None = None,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.schema_ready():
            return {"id": "skipped"}
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.policy_decisions (
                        id, org_id, object_type, object_id, action, decision,
                        policy_code, risk_level, approval_chain, input_context, reason, actor_id
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s::uuid, %s, %s,
                        %s, %s, %s::jsonb, %s::jsonb, %s, %s::uuid
                    )
                    RETURNING id::text, decision, policy_code, evaluated_at
                    """,
                    (
                        row_id,
                        org_id,
                        object_type,
                        object_id,
                        action,
                        decision,
                        policy_code,
                        risk_level,
                        Json(approval_chain or []),
                        Json(input_context or {}),
                        reason,
                        actor_id,
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_decisions(
        self,
        org_id: str,
        *,
        action: str | None = None,
        object_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if action:
            clauses.append("action = %s")
            params.append(action)
        if object_type:
            clauses.append("object_type = %s")
            params.append(object_type)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, object_type, object_id::text, action, decision,
                           policy_code, risk_level, approval_chain, reason, actor_id::text, evaluated_at
                    FROM governance.policy_decisions
                    WHERE {' AND '.join(clauses)}
                    ORDER BY evaluated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]


policy_decision_repository = PolicyDecisionRepository()
