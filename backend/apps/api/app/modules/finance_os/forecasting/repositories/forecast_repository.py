from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ForecastRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'finance_os' AND table_name = 'forecasts'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None

    def upsert(
        self,
        org_id: str,
        *,
        forecast_type: str,
        horizon_days: int,
        as_of_date: str,
        forecast_date: str,
        forecast_value: float,
        confidence_score: float,
        confidence_band: str,
        model_version: str = "rule_v1",
        inputs: dict | None = None,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.forecasts (
                      id, org_id, forecast_type, horizon_days, as_of_date, forecast_date,
                      forecast_value, confidence_score, confidence_band, model_version, inputs
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s, %s, %s::date, %s::date,
                      %s::numeric, %s::numeric, %s, %s, %s::jsonb
                    )
                    ON CONFLICT (org_id, forecast_type, horizon_days, as_of_date, forecast_date)
                    DO UPDATE SET
                      forecast_value = EXCLUDED.forecast_value,
                      confidence_score = EXCLUDED.confidence_score,
                      confidence_band = EXCLUDED.confidence_band,
                      model_version = EXCLUDED.model_version,
                      inputs = EXCLUDED.inputs,
                      generated_at = now()
                    RETURNING id::text, forecast_type, horizon_days, as_of_date::text, forecast_date::text, forecast_value
                    """,
                    (
                        row_id,
                        org_id,
                        forecast_type,
                        int(horizon_days),
                        as_of_date,
                        forecast_date,
                        float(forecast_value),
                        float(confidence_score),
                        confidence_band,
                        model_version,
                        Json(inputs or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_latest(
        self,
        org_id: str,
        *,
        forecast_type: str,
        horizon_days: int,
        as_of_date: str | None = None,
        limit: int = 400,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 400), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if as_of_date:
                    cur.execute(
                        """
                        SELECT id::text, forecast_type, horizon_days, as_of_date::text, forecast_date::text,
                               forecast_value, confidence_score, confidence_band, model_version, inputs,
                               generated_at::text
                        FROM finance_os.forecasts
                        WHERE org_id = %s::uuid AND forecast_type = %s AND horizon_days = %s AND as_of_date = %s::date
                        ORDER BY forecast_date ASC
                        LIMIT %s
                        """,
                        (org_id, forecast_type, int(horizon_days), as_of_date, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, forecast_type, horizon_days, as_of_date::text, forecast_date::text,
                               forecast_value, confidence_score, confidence_band, model_version, inputs,
                               generated_at::text
                        FROM finance_os.forecasts
                        WHERE org_id = %s::uuid AND forecast_type = %s AND horizon_days = %s
                          AND as_of_date = (
                            SELECT MAX(as_of_date) FROM finance_os.forecasts
                            WHERE org_id = %s::uuid AND forecast_type = %s AND horizon_days = %s
                          )
                        ORDER BY forecast_date ASC
                        LIMIT %s
                        """,
                        (org_id, forecast_type, int(horizon_days), org_id, forecast_type, int(horizon_days), limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def distinct_latest_as_of(self, org_id: str, *, forecast_type: str) -> str | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT MAX(as_of_date)::text AS as_of_date
                    FROM finance_os.forecasts
                    WHERE org_id = %s::uuid AND forecast_type = %s
                    """,
                    (org_id, forecast_type),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return str(row.get("as_of_date")) if isinstance(row, dict) else str(row[0])


forecast_repository = ForecastRepository()

