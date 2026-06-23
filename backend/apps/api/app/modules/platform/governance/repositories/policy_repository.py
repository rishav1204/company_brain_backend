from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PolicyRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'governance' AND table_name = 'policy_rules'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def list_active(self, org_id: str, *, policy_type: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        clauses = ["org_id = %s::uuid", "is_active = TRUE"]
        params: list[Any] = [org_id]
        if policy_type:
            clauses.append("policy_type = %s")
            params.append(policy_type)
        where = " AND ".join(clauses)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, org_id::text, policy_key, policy_type, conditions, actions,
                           is_active, priority, created_at, updated_at
                    FROM governance.policy_rules
                    WHERE {where}
                    ORDER BY priority ASC, policy_key ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]

    def upsert(
        self,
        org_id: str,
        *,
        policy_key: str,
        policy_type: str,
        conditions: dict,
        actions: dict,
        is_active: bool = True,
        priority: int = 100,
    ) -> dict[str, Any]:
        rule_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.policy_rules (
                        id, org_id, policy_key, policy_type, conditions, actions, is_active, priority
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                    ON CONFLICT (org_id, policy_key) DO UPDATE SET
                        policy_type = EXCLUDED.policy_type,
                        conditions = EXCLUDED.conditions,
                        actions = EXCLUDED.actions,
                        is_active = EXCLUDED.is_active,
                        priority = EXCLUDED.priority,
                        updated_at = NOW()
                    RETURNING id::text, policy_key, policy_type, conditions, actions, is_active, priority
                    """,
                    (
                        rule_id,
                        org_id,
                        policy_key,
                        policy_type,
                        Json(conditions),
                        Json(actions),
                        is_active,
                        priority,
                    ),
                )
                return dict(cur.fetchone() or {})


policy_repository = PolicyRepository()
