from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.erp.reporting.security.reporting_guard import require_reporting_read
from app.modules.erp.reporting.services.treasury_report_service import treasury_report_service
from app.modules.erp.reporting.events.report_events import emit_report_generated

router = APIRouter(prefix="/treasury", tags=["erp-reports-treasury"])


@router.get("/cash-position")
def treasury_cash_position(context=Depends(build_request_context)) -> dict:
    require_reporting_read(context.user)
    item = treasury_report_service.cash_position(context.org_id)
    emit_report_generated(context.org_id, report_type="treasury_cash")
    return {"request_id": context.request_id, "item": item}


@router.get("/liquidity")
def treasury_liquidity(context=Depends(build_request_context)) -> dict:
    require_reporting_read(context.user)
    item = treasury_report_service.liquidity(context.org_id)
    emit_report_generated(context.org_id, report_type="treasury_liquidity")
    return {"request_id": context.request_id, "item": item}
