from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AITraceRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'audit' AND table_name = 'ai_reasoning_traces'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def append(
        self,
        org_id: str,
        *,
        prompt_hash: str,
        reasoning_summary: str,
        confidence_score: float | None,
        decision: dict,
        retrieved_context: dict | None = None,
        policy_checks: list | None = None,
        agent_run_id: str | None = None,
        workflow_id: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        trace_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit.ai_reasoning_traces (
                        id, org_id, agent_run_id, workflow_id, step_id,
                        prompt_hash, retrieved_context, reasoning_summary,
                        confidence_score, decision, policy_checks
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                        %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb
                    )
                    RETURNING id::text, prompt_hash, reasoning_summary, confidence_score, created_at
                    """,
                    (
                        trace_id,
                        org_id,
                        agent_run_id,
                        workflow_id,
                        step_id,
                        prompt_hash,
                        Json(retrieved_context or {}),
                        reasoning_summary[:4000],
                        confidence_score,
                        Json(decision),
                        Json(policy_checks or []),
                    ),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, trace_id: str) -> dict[str, Any] | None:
        if not self.schema_ready():
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, agent_run_id::text, workflow_id::text, prompt_hash,
                           retrieved_context, reasoning_summary, confidence_score, decision,
                           policy_checks, created_at
                    FROM audit.ai_reasoning_traces
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, trace_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


ai_trace_repository = AITraceRepository()
