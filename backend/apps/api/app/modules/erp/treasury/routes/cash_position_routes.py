from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.treasury.ai.treasury_copilot import answer_treasury_question
from app.modules.erp.treasury.schemas.treasury_schema import TreasuryCopilotRequest
from app.modules.erp.treasury.security.treasury_access import enforce_treasury_action
from app.modules.erp.treasury.security.treasury_guard import require_treasury_read
from app.modules.erp.treasury.services.cash_position_service import cash_position_service
from app.modules.erp.treasury.services.funding_service import dashboard_service
from app.modules.erp.treasury.services.liquidity_service import liquidity_service

router = APIRouter()


@router.get("/cash-position")
def cash_position(context=Depends(require_treasury_read)) -> dict:
    live = cash_position_service.compute_live_position(context.org_id)
    history = cash_position_service.history(context.org_id, limit=30)
    return {"request_id": context.request_id, "live": live, "snapshots": history}


@router.get("/cash-position/history")
def cash_position_history(
    context=Depends(require_treasury_read),
    bank_account_id: str | None = Query(default=None),
    limit: int = Query(default=90, ge=1, le=365),
) -> dict:
    items = cash_position_service.history(context.org_id, bank_account_id=bank_account_id, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/position")
def cash_position_legacy(context=Depends(require_treasury_read)) -> dict:
    item = cash_position_service.compute_live_position(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/liquidity")
def liquidity(context=Depends(require_treasury_read)) -> dict:
    item = liquidity_service.analyze(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/forecast")
def forecast(context=Depends(require_treasury_read), horizon_days: int = Query(default=30, ge=7, le=180)) -> dict:
    from app.modules.erp.treasury.services.treasury_forecast_service import treasury_forecast_service

    item = treasury_forecast_service.build_forecast(context.org_id, horizon_days=horizon_days)
    stored = treasury_forecast_service.list_stored(context.org_id, horizon_days=horizon_days)
    return {"request_id": context.request_id, "item": item, "stored": stored}


@router.get("/dashboard")
def dashboard(context=Depends(require_treasury_read)) -> dict:
    item = dashboard_service.build(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/copilot")
def treasury_copilot(request: TreasuryCopilotRequest, context=Depends(require_treasury_read)) -> dict:
    enforce_treasury_action(context, action="treasury.copilot.query", object_type="treasury", object_id="copilot")
    position = cash_position_service.compute_live_position(context.org_id)
    liquidity = liquidity_service.analyze(context.org_id)
    item = answer_treasury_question(question=request.question, position=position, liquidity=liquidity)
    return {"request_id": context.request_id, "item": item}
