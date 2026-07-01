from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.repositories.dashboard_snapshot_repository import dashboard_snapshot_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.services.cache.redis_cache import cache_hit_metric, cache_miss_metric, get_cached, invalidate_namespace, set_cached
from app.services.db import get_db_conn, set_rls_org


class ExecutiveDashboardService:
    def get(self, org_id: str, *, snapshot_date: str | None = None) -> dict:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        snap = snapshot_date or date.today().isoformat()
        cache_params = {"snapshot_date": snap}
        cached_redis = get_cached(org_id, "analytics.dashboard", cache_params)
        if cached_redis is not None:
            cache_hit_metric("analytics.dashboard")
            return cached_redis
        cache_miss_metric("analytics.dashboard")

        cached = dashboard_snapshot_repository.get_latest(org_id, snapshot_date=snap if snapshot_date else None)
        if cached:
            payload = cached.get("payload") or {}
            result = {
                "snapshot_date": cached.get("snapshot_date"),
                "refreshed_at": cached.get("refreshed_at"),
                **payload,
            }
            set_cached(org_id, "analytics.dashboard", result, cache_params)
            return result
        result = self._build_live(org_id, snapshot_date=snap)
        set_cached(org_id, "analytics.dashboard", result, cache_params)
        return result

    def _build_live(self, org_id: str, *, snapshot_date: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT kpi_code, kpi_value, snapshot_date::text, metadata, created_at::text
                    FROM finance_analytics.kpi_snapshots
                    WHERE org_id = %s::uuid AND snapshot_date = %s::date
                    ORDER BY kpi_code ASC
                    LIMIT %s
                    """,
                    (org_id, snapshot_date, 50),
                )
                kpis = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT kpi_code, trend_direction, trend_percent, period_key, created_at::text
                    FROM finance_analytics.kpi_trends
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, 20),
                )
                trends = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT id::text, insight_type, title, description, severity, generated_at::text
                    FROM finance_analytics.executive_insights
                    WHERE org_id = %s::uuid
                    ORDER BY generated_at DESC
                    LIMIT %s
                    """,
                    (org_id, 10),
                )
                insights = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT id::text, anomaly_type, severity, payload, detected_at::text
                    FROM finance_analytics.anomaly_flags
                    WHERE org_id = %s::uuid
                    ORDER BY detected_at DESC LIMIT %s
                    """,
                    (org_id, 10),
                )
                anomalies = [dict(row) for row in cur.fetchall()]
        by_code = {k["kpi_code"]: k for k in kpis}
        return {
            "snapshot_date": snapshot_date,
            "widgets": {
                "cash_position": by_code.get("treasury.cash_runway_days"),
                "liquidity_coverage": by_code.get("treasury.liquidity_coverage"),
                "revenue_trend": by_code.get("finance.net_profit_margin"),
                "collection_efficiency": by_code.get("collections.dso"),
                "vendor_exposure": by_code.get("vendor.dpo"),
                "compliance_health": by_code.get("compliance.filing_pct"),
                "close_status": by_code.get("close.efficiency_score"),
                "forecast_accuracy": by_code.get("forecast.accuracy_avg"),
            },
            "trends": trends[:10],
            "top_risks": [i for i in insights if i.get("severity") in {"high", "warning"}][:5],
            "top_opportunities": [i for i in insights if i.get("severity") == "info"][:5],
            "anomalies": anomalies,
            "cash_flow_status": "phase2",
        }

    def build_and_cache(self, org_id: str, *, snapshot_date: str | None = None) -> dict:
        snap = (snapshot_date or date.today().isoformat())[:10]
        payload = self._build_live(org_id, snapshot_date=snap)
        dashboard_snapshot_repository.upsert(org_id, snapshot_date=snap, payload=payload)
        invalidate_namespace(org_id, "analytics")
        return payload


executive_dashboard_service = ExecutiveDashboardService()
