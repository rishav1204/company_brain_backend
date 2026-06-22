from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.reporting.schemas.reporting_schema import TaxSummaryResponse
from app.modules.erp.reporting.security.reporting_guard import require_reporting_read
from app.modules.erp.reporting.services.gst_report_service import gst_report_service
from app.modules.erp.reporting.events.report_events import emit_report_generated

router = APIRouter(tags=["erp-reports-gst"])


@router.get("/gst", response_model=TaxSummaryResponse)
def gst_report(
    return_period: str = Query(...),
    return_type: str = Query("GSTR-3B"),
    context=Depends(build_request_context),
) -> TaxSummaryResponse:
    require_reporting_read(context.user)
    item = gst_report_service.get(context.org_id, return_period=return_period, return_type=return_type)
    emit_report_generated(context.org_id, report_type="gst")
    return TaxSummaryResponse(
        return_period=item.get("return_period") or return_period,
        type_value=item.get("type_value") or return_type,
        payload=item.get("payload") or {},
        refreshed_at=item.get("refreshed_at"),
    )
