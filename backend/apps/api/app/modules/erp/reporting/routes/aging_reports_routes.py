from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.reporting.schemas.reporting_schema import AgingReportResponse
from app.modules.erp.reporting.security.reporting_guard import require_reporting_read
from app.modules.erp.reporting.services.aging_report_service import aging_report_service
from app.modules.erp.reporting.events.report_events import emit_report_generated

router = APIRouter(tags=["erp-reports-aging"])


@router.get("/ap-aging", response_model=AgingReportResponse)
def ap_aging(
    as_of_date: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    context=Depends(build_request_context),
) -> AgingReportResponse:
    require_reporting_read(context.user)
    item = aging_report_service.get_ap(context.org_id, as_of_date=as_of_date, cursor=cursor, limit=limit)
    emit_report_generated(context.org_id, report_type="ap_aging")
    return AgingReportResponse(**item)


@router.get("/ar-aging", response_model=AgingReportResponse)
def ar_aging(
    as_of_date: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    context=Depends(build_request_context),
) -> AgingReportResponse:
    require_reporting_read(context.user)
    item = aging_report_service.get_ar(context.org_id, as_of_date=as_of_date, cursor=cursor, limit=limit)
    emit_report_generated(context.org_id, report_type="ar_aging")
    return AgingReportResponse(**item)
