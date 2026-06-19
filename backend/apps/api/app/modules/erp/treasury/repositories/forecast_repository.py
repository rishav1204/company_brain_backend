from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ForecastRepository:
    def save(self, org_id: str, *, forecast: dict) -> dict:
        fid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.cash_forecasts (
                      id, org_id, forecast_date, horizon_days,
                      expected_inflows, expected_outflows, forecast_cash_balance, confidence_score, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, horizon_days, forecast_cash_balance
                    """,
                    (
                        fid, org_id, forecast["forecast_date"], forecast["horizon_days"],
                        forecast["expected_inflows"], forecast["expected_outflows"],
                        forecast["forecast_cash_balance"], forecast["confidence_score"],
                        Json(forecast.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": fid})

    def list_latest(self, org_id: str, *, horizon_days: int | None = None, limit: int = 10) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if horizon_days:
            where.append("horizon_days = %s")
            params.append(horizon_days)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, forecast_date::text, horizon_days,
                           expected_inflows, expected_outflows, forecast_cash_balance, confidence_score, created_at::text
                    FROM erp.cash_forecasts
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


forecast_repository = ForecastRepository()
