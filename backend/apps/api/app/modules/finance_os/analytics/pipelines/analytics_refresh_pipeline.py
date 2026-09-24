from __future__ import annotations

from app.modules.finance_os.analytics.engine import analytics_engine
from app.modules.finance_os.analytics.events.analytics_events import (
    emit_analytics_refresh_requested,
    emit_dashboard_refreshed,
    emit_insight_generated,
    emit_kpi_updated,
    emit_risk_detected,
)
from app.modules.finance_os.analytics.repositories.anomaly_flag_repository import anomaly_flag_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.modules.finance_os.analytics.services.executive_dashboard_service import executive_dashboard_service


def run_refresh(org_id: str, *, fiscal_period_id: str | None = None, trace_id: str | None = None) -> dict:
    if not analytics_schema_repository.schema_ready():
        return {"status": "skipped", "reason": "schema_not_ready"}
    try:
        from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import (
            bootstrap_wave1_boundaries,
            is_bootstrapped,
        )

        if not is_bootstrapped():
            bootstrap_wave1_boundaries()
    except Exception:
        pass
    emit_analytics_refresh_requested(org_id, reason="pipeline", trace_id=trace_id)
    result = analytics_engine.refresh_kpis(org_id, fiscal_period_id=fiscal_period_id)
    emit_kpi_updated(org_id, count=int(result.get("kpis") or 0), trace_id=trace_id)
    emit_insight_generated(org_id, count=int(result.get("insights") or 0), trace_id=trace_id)
    for flag in anomaly_flag_repository.list_recent(org_id, limit=5):
        emit_risk_detected(org_id, anomaly_type=str(flag.get("anomaly_type")), severity=str(flag.get("severity")), trace_id=trace_id)
    dash = executive_dashboard_service.build_and_cache(org_id, snapshot_date=result.get("snapshot_date"))
    emit_dashboard_refreshed(org_id, snapshot_date=str(result.get("snapshot_date")), trace_id=trace_id)
    return {"status": "completed", "kpis": result, "dashboard": {"snapshot_date": dash.get("snapshot_date")}}
