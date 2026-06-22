from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ForecastAccuracyRepository:
    def create(
        self,
        org_id: str,
        *,
        forecast_id: str,
        actual_value: float,
        forecast_value: float,
        variance_percent: float,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.forecast_accuracy (
                      id, org_id, forecast_id, actual_value, forecast_value, variance_percent
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::numeric, %s::numeric, %s::numeric)
                    RETURNING id::text, forecast_id::text, variance_percent, calculated_at::text
                    """,
                    (row_id, org_id, forecast_id, float(actual_value), float(forecast_value), float(variance_percent)),
                )
                return dict(cur.fetchone() or {})

    def list_for_forecast(self, org_id: str, *, forecast_id: str, limit: int = 30) -> list[dict]:
        limit = max(1, min(int(limit or 30), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, actual_value, forecast_value, variance_percent, calculated_at::text
                    FROM finance_os.forecast_accuracy
                    WHERE org_id = %s::uuid AND forecast_id = %s::uuid
                    ORDER BY calculated_at DESC
                    LIMIT %s
                    """,
                    (org_id, forecast_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


accuracy_repository = ForecastAccuracyRepository()

