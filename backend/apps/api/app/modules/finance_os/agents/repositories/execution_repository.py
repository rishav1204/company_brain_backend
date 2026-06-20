from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ExecutionRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'finance_os' AND table_name = 'agent_executions'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None

    def create(
        self,
        org_id: str,
        *,
        agent_name: str,
        trigger_type: str,
        task_type: str | None = None,
        source_event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
        platform_run_id: str | None = None,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.agent_executions (
                        id, org_id, platform_run_id, agent_name, task_type, trigger_type,
                        status, source_event_type, entity_type, entity_id, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, 'running', %s, %s, %s, %s::jsonb)
                    RETURNING id::text, agent_name, status, started_at::text
                    """,
                    (
                        row_id,
                        org_id,
                        platform_run_id,
                        agent_name,
                        task_type,
                        trigger_type,
                        source_event_type,
                        entity_type,
                        entity_id,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def update_status(
        self,
        org_id: str,
        execution_id: str,
        *,
        status: str,
        metadata: dict | None = None,
        platform_run_id: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.agent_executions
                    SET status = %s,
                        completed_at = CASE WHEN %s IN ('completed','failed','cancelled','pending_approval') THEN now() ELSE completed_at END,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                        platform_run_id = COALESCE(%s::uuid, platform_run_id)
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text, status, platform_run_id::text, completed_at::text
                    """,
                    (status, status, Json(metadata or {}), platform_run_id, execution_id, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get(self, org_id: str, execution_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, platform_run_id::text, agent_name, task_type,
                           trigger_type, status, source_event_type, entity_type, entity_id,
                           metadata, started_at::text, completed_at::text, created_at::text
                    FROM finance_os.agent_executions
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (execution_id, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        agent_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if agent_name:
            clauses.append("agent_name = %s")
            params.append(agent_name)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, agent_name, task_type, trigger_type, status, entity_type, entity_id,
                           started_at::text, completed_at::text
                    FROM finance_os.agent_executions
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]

    def summary(self, org_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*)::int AS cnt
                    FROM finance_os.agent_executions
                    WHERE org_id = %s::uuid
                    GROUP BY status
                    """,
                    (org_id,),
                )
                by_status = {row["status"]: row["cnt"] for row in cur.fetchall()}
                cur.execute(
                    """
                    SELECT agent_name, COUNT(*)::int AS cnt
                    FROM finance_os.agent_executions
                    WHERE org_id = %s::uuid
                    GROUP BY agent_name
                    """,
                    (org_id,),
                )
                by_agent = {row["agent_name"]: row["cnt"] for row in cur.fetchall()}
        return {"by_status": by_status, "by_agent": by_agent}


execution_repository = ExecutionRepository()
