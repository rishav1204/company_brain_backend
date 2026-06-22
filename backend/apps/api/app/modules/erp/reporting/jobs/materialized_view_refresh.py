from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository


def run_mv_refresh(org_id: str, *, fiscal_period_id: str | None = None) -> dict:
    if not reporting_schema_repository.schema_ready():
        return {"status": "skipped"}
    if fiscal_period_id:
        return materialization_engine.refresh_all_for_period(org_id, fiscal_period_id=fiscal_period_id)
    from datetime import date

    as_of = date.today().isoformat()
    return {
        "ap_aging": materialization_engine.refresh_ap_aging(org_id, as_of_date=as_of),
        "ar_aging": materialization_engine.refresh_ar_aging(org_id, as_of_date=as_of),
    }
