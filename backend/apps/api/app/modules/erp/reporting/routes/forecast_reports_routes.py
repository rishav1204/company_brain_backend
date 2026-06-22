from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.reporting.security.reporting_guard import require_reporting_read
from app.modules.erp.reporting.services.forecast_report_service import forecast_report_service
from app.modules.erp.reporting.events.report_events import emit_report_generated

router = APIRouter(prefix="/forecast", tags=["erp-reports-forecast"])


@router.get("/")
def forecast_report(
    type: str = Query("cash", alias="type"),
    horizon_days: int = 30,
    as_of_date: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_reporting_read(context.user)
    item = forecast_report_service.get(
        context.org_id, forecast_type=type, horizon_days=horizon_days, as_of_date=as_of_date
    )
    emit_report_generated(context.org_id, report_type=f"forecast_{type}")
    return {"request_id": context.request_id, "item": item}
