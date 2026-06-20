from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class RecommendationRepository:
    def create(
        self,
        org_id: str,
        *,
        execution_id: str,
        recommendation_type: str,
        recommendation: str,
        confidence_score: float,
        confidence_band: str,
        approval_required: bool = True,
        workflow_instance_id: str | None = None,
        metadata: dict | None = None,
        status: str = "proposed",
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.agent_recommendations (
                        id, org_id, execution_id, recommendation_type, recommendation,
                        confidence_score, confidence_band, approval_required,
                        workflow_instance_id, metadata, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s::jsonb, %s)
                    RETURNING id::text, recommendation_type, confidence_score, confidence_band, status
                    """,
                    (
                        row_id,
                        org_id,
                        execution_id,
                        recommendation_type,
                        recommendation,
                        confidence_score,
                        confidence_band,
                        approval_required,
                        workflow_instance_id,
                        Json(metadata or {}),
                        status,
                    ),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, recommendation_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, execution_id::text, recommendation_type, recommendation,
                           confidence_score, confidence_band, approval_required,
                           workflow_instance_id::text, metadata, status, created_at::text
                    FROM finance_os.agent_recommendations
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (recommendation_id, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_for_execution(self, org_id: str, execution_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, recommendation_type, recommendation, confidence_score,
                           confidence_band, approval_required, workflow_instance_id::text, status
                    FROM finance_os.agent_recommendations
                    WHERE org_id = %s::uuid AND execution_id = %s::uuid
                    ORDER BY created_at
                    """,
                    (org_id, execution_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        agent_name: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = ["r.org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            clauses.append("r.status = %s")
            params.append(status)
        if agent_name:
            clauses.append("e.agent_name = %s")
            params.append(agent_name)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT r.id::text, r.recommendation_type, r.recommendation, r.confidence_score,
                           r.confidence_band, r.status, e.agent_name, r.execution_id::text
                    FROM finance_os.agent_recommendations r
                    JOIN finance_os.agent_executions e ON e.id = r.execution_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]

    def update_status(self, org_id: str, recommendation_id: str, *, status: str, workflow_instance_id: str | None = None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.agent_recommendations
                    SET status = %s,
                        workflow_instance_id = COALESCE(%s::uuid, workflow_instance_id)
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text, status, workflow_instance_id::text
                    """,
                    (status, workflow_instance_id, recommendation_id, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


recommendation_repository = RecommendationRepository()
