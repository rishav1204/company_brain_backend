from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class RecommendationRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        rec_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.workflow_recommendations (
                        id, org_id, workflow_type, workflow_instance_id, recommendation_type,
                        recommendation, impact_score, status, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, workflow_type, recommendation_type, recommendation,
                              impact_score::float8 AS impact_score, status
                    """,
                    (
                        rec_id,
                        org_id,
                        data["workflow_type"],
                        data.get("workflow_instance_id"),
                        data["recommendation_type"],
                        data["recommendation"],
                        data.get("impact_score", 0),
                        data.get("status", "open"),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_open(self, org_id: str, *, workflow_type: str | None = None, limit: int = 50) -> list[dict]:
        where = ["org_id = %s::uuid", "status = 'open'"]
        params: list = [org_id]
        if workflow_type:
            where.append("workflow_type = %s")
            params.append(workflow_type)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, workflow_type, workflow_instance_id::text AS workflow_instance_id,
                           recommendation_type, recommendation, impact_score::float8 AS impact_score,
                           status, metadata, created_at::text
                    FROM finance_os.workflow_recommendations
                    WHERE {' AND '.join(where)}
                    ORDER BY impact_score DESC, created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def update_status(
        self,
        org_id: str,
        recommendation_id: str,
        *,
        status: str,
        accepted_by: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.workflow_recommendations
                    SET status = %s, accepted_by = %s::uuid,
                        accepted_at = CASE WHEN %s IN ('accepted','rejected','dismissed') THEN NOW() ELSE accepted_at END
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, recommendation_type, recommendation, impact_score::float8 AS impact_score
                    """,
                    (status, accepted_by, status, org_id, recommendation_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


recommendation_repository = RecommendationRepository()
