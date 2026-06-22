from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.events.report_events import emit_report_generated, emit_reports_refresh_requested
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository


def run_refresh(org_id: str, *, fiscal_period_id: str | None = None, trace_id: str | None = None) -> dict:
    if not reporting_schema_repository.schema_ready():
        return {"status": "skipped", "reason": "schema_not_ready"}
    emit_reports_refresh_requested(org_id, reason="pipeline", trace_id=trace_id)
    if fiscal_period_id:
        result = materialization_engine.refresh_all_for_period(org_id, fiscal_period_id=fiscal_period_id)
    else:
        from datetime import date

        as_of = date.today().isoformat()
        result = {
            "refreshed": [
                materialization_engine.refresh_ap_aging(org_id, as_of_date=as_of),
                materialization_engine.refresh_ar_aging(org_id, as_of_date=as_of),
            ]
        }
    emit_report_generated(org_id, report_type="refresh_all", trace_id=trace_id)
    return {"status": "completed", **result}
