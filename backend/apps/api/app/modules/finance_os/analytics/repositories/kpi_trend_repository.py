from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class KpiTrendRepository:
    def upsert(
        self,
        org_id: str,
        *,
        kpi_code: str,
        trend_direction: str,
        trend_percent: float,
        period_key: str,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_analytics.kpi_trends (
                      org_id, kpi_code, trend_direction, trend_percent, period_key
                    )
                    VALUES (%s::uuid, %s, %s, %s::numeric, %s)
                    ON CONFLICT (org_id, kpi_code, period_key)
                    DO UPDATE SET trend_direction = EXCLUDED.trend_direction,
                                  trend_percent = EXCLUDED.trend_percent,
                                  created_at = now()
                    RETURNING kpi_code, trend_direction, trend_percent, period_key
                    """,
                    (org_id, kpi_code, trend_direction, float(trend_percent), period_key),
                )
                return dict(cur.fetchone() or {})

    def list(
        self,
        org_id: str,
        *,
        kpi_code: str | None = None,
        period_key: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if kpi_code and period_key:
                    cur.execute(
                        """
                        SELECT kpi_code, trend_direction, trend_percent, period_key, created_at::text
                        FROM finance_analytics.kpi_trends
                        WHERE org_id = %s::uuid AND kpi_code = %s AND period_key = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, kpi_code, period_key, limit),
                    )
                elif kpi_code:
                    cur.execute(
                        """
                        SELECT kpi_code, trend_direction, trend_percent, period_key, created_at::text
                        FROM finance_analytics.kpi_trends
                        WHERE org_id = %s::uuid AND kpi_code = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, kpi_code, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT kpi_code, trend_direction, trend_percent, period_key, created_at::text
                        FROM finance_analytics.kpi_trends
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]


kpi_trend_repository = KpiTrendRepository()
