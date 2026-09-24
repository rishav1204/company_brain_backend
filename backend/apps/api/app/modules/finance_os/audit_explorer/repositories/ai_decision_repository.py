from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.modules.finance_os.audit_explorer.repositories.schema_repository import audit_schema_repository
from app.modules.finance_os.audit_explorer.validators.ai_context_validator import validate_ai_context
from app.services.db import get_db_conn, set_rls_org


class AIDecisionRepository:
    def schema_ready(self) -> bool:
        return audit_schema_repository.schema_ready()

    def upsert(
        self,
        org_id: str,
        *,
        decision_type: str,
        reasoning_summary: str,
        input_context: dict | None = None,
        agent_execution_id: str | None = None,
        ai_trace_id: str | None = None,
        recommendation_id: str | None = None,
        confidence_score: float | None = None,
        outcome: str | None = None,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        if not self.schema_ready():
            return {"id": "skipped"}
        safe_context = validate_ai_context(input_context)
        summary = (reasoning_summary or "")[:4000]
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if ai_trace_id:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.ai_decision_trails (
                            id, org_id, agent_execution_id, ai_trace_id, recommendation_id,
                            decision_type, input_context, reasoning_summary, confidence_score,
                            outcome, approved_by
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                            %s, %s::jsonb, %s, %s, %s, %s::uuid
                        )
                        ON CONFLICT DO NOTHING
                        RETURNING id::text, decision_type, confidence_score, outcome
                        """,
                        (
                            row_id,
                            org_id,
                            agent_execution_id,
                            ai_trace_id,
                            recommendation_id,
                            decision_type,
                            Json(safe_context),
                            summary,
                            confidence_score,
                            outcome,
                            approved_by,
                        ),
                    )
                elif recommendation_id:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.ai_decision_trails (
                            id, org_id, agent_execution_id, ai_trace_id, recommendation_id,
                            decision_type, input_context, reasoning_summary, confidence_score,
                            outcome, approved_by
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s::uuid, NULL, %s::uuid,
                            %s, %s::jsonb, %s, %s, %s, %s::uuid
                        )
                        ON CONFLICT DO NOTHING
                        RETURNING id::text, decision_type, confidence_score, outcome
                        """,
                        (
                            row_id,
                            org_id,
                            agent_execution_id,
                            recommendation_id,
                            decision_type,
                            Json(safe_context),
                            summary,
                            confidence_score,
                            outcome,
                            approved_by,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.ai_decision_trails (
                            id, org_id, agent_execution_id, decision_type, input_context,
                            reasoning_summary, confidence_score, outcome, approved_by
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, %s, %s, %s, %s::uuid
                        )
                        RETURNING id::text, decision_type, confidence_score, outcome
                        """,
                        (
                            row_id,
                            org_id,
                            agent_execution_id,
                            decision_type,
                            Json(safe_context),
                            summary,
                            confidence_score,
                            outcome,
                            approved_by,
                        ),
                    )
                row = cur.fetchone()
                if row:
                    return dict(row)
                if ai_trace_id:
                    cur.execute(
                        """
                        SELECT id::text, decision_type, confidence_score, outcome
                        FROM finance_audit.ai_decision_trails
                        WHERE org_id = %s::uuid AND ai_trace_id = %s::uuid
                        LIMIT 1
                        """,
                        (org_id, ai_trace_id),
                    )
                elif recommendation_id:
                    cur.execute(
                        """
                        SELECT id::text, decision_type, confidence_score, outcome
                        FROM finance_audit.ai_decision_trails
                        WHERE org_id = %s::uuid AND recommendation_id = %s::uuid
                        LIMIT 1
                        """,
                        (org_id, recommendation_id),
                    )
                existing = cur.fetchone()
                return dict(existing) if existing else {"id": row_id}

    def get_by_execution(self, org_id: str, execution_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, agent_execution_id::text, ai_trace_id::text,
                           recommendation_id::text, decision_type, input_context,
                           reasoning_summary, confidence_score, outcome,
                           approved_by::text, created_at
                    FROM finance_audit.ai_decision_trails
                    WHERE org_id = %s::uuid AND agent_execution_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, execution_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


ai_decision_repository = AIDecisionRepository()
