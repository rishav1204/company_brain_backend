from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ForecastExplanationRepository:
    def create(self, org_id: str, *, forecast_id: str, explanation: str, evidence: dict | None = None) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.forecast_explanations (id, org_id, forecast_id, explanation, evidence)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
                    RETURNING id::text, forecast_id::text, created_at::text
                    """,
                    (row_id, org_id, forecast_id, explanation, Json(evidence or {})),
                )
                return dict(cur.fetchone() or {})

    def get_latest_for_forecast(self, org_id: str, *, forecast_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, forecast_id::text, explanation, evidence, created_at::text
                    FROM finance_os.forecast_explanations
                    WHERE org_id = %s::uuid AND forecast_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, forecast_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


explanation_repository = ForecastExplanationRepository()

