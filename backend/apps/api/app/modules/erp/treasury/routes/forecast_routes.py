from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.treasury.security.treasury_guard import require_treasury_read
from app.modules.erp.treasury.services.treasury_forecast_service import treasury_forecast_service

router = APIRouter()


@router.get("/cashflow/forecast")
def cashflow_forecast_legacy(context=Depends(require_treasury_read), horizon_days: int = Query(default=30, ge=7, le=365)) -> dict:
    item = treasury_forecast_service.build_forecast(context.org_id, horizon_days=horizon_days)
    return {"request_id": context.request_id, "item": item}
