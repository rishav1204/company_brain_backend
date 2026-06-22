from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.repositories.anomaly_flag_repository import anomaly_flag_repository
from app.modules.finance_os.analytics.repositories.dashboard_snapshot_repository import dashboard_snapshot_repository
from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.kpi_trend_repository import kpi_trend_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


class ExecutiveDashboardService:
    def get(self, org_id: str, *, snapshot_date: str | None = None) -> dict:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        snap = snapshot_date or date.today().isoformat()
        cached = dashboard_snapshot_repository.get_latest(org_id, snapshot_date=snap if snapshot_date else None)
        if cached:
            payload = cached.get("payload") or {}
            return {
                "snapshot_date": cached.get("snapshot_date"),
                "refreshed_at": cached.get("refreshed_at"),
                **payload,
            }
        return self._build_live(org_id, snapshot_date=snap)

    def _build_live(self, org_id: str, *, snapshot_date: str) -> dict:
        kpis = kpi_snapshot_repository.list(org_id, snapshot_date=snapshot_date, limit=50)
        trends = kpi_trend_repository.list(org_id, limit=20)
        insights = insight_repository.list(org_id, limit=10)
        anomalies = anomaly_flag_repository.list_recent(org_id, limit=10)
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
        return payload


executive_dashboard_service = ExecutiveDashboardService()
