from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class InsightRepository:
    def create(
        self,
        org_id: str,
        *,
        insight_type: str,
        title: str,
        description: str,
        severity: str = "info",
        evidence: dict | None = None,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_analytics.executive_insights (
                      id, org_id, insight_type, title, description, severity, evidence
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id::text, insight_type, title, severity, generated_at::text
                    """,
                    (row_id, org_id, insight_type, title, description, severity, Json(evidence or {})),
                )
                return dict(cur.fetchone() or {"id": row_id})

    def list(
        self,
        org_id: str,
        *,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if severity:
                    cur.execute(
                        """
                        SELECT id::text, insight_type, title, description, severity, evidence, generated_at::text
                        FROM finance_analytics.executive_insights
                        WHERE org_id = %s::uuid AND severity = %s
                        ORDER BY generated_at DESC LIMIT %s
                        """,
                        (org_id, severity, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, insight_type, title, description, severity, evidence, generated_at::text
                        FROM finance_analytics.executive_insights
                        WHERE org_id = %s::uuid
                        ORDER BY generated_at DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]


insight_repository = InsightRepository()
