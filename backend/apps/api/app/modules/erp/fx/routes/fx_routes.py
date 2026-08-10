from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.fx.schemas.fx_schema import (
    ExchangeRateCreateRequest,
    ExchangeRateUpdateRequest,
    FxRevaluationRunRequest,
)
from app.modules.erp.fx.security.fx_guard import require_fx_admin, require_fx_read
from app.modules.erp.fx.services.exchange_rate_service import exchange_rate_service
from app.modules.erp.fx.services.fx_revaluation_service import fx_revaluation_service

router = APIRouter()


@router.post("/exchange-rates")
def create_exchange_rate(request: ExchangeRateCreateRequest, context=Depends(require_fx_admin)) -> dict:
    try:
        item = exchange_rate_service.create_rate(
            context.org_id,
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            rate=request.rate,
            rate_date=request.rate_date,
            source=request.source,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/exchange-rates")
def list_exchange_rates(
    context=Depends(require_fx_read),
    from_currency: str | None = Query(default=None),
    to_currency: str | None = Query(default=None),
    company_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    items = exchange_rate_service.list_rates(
        context.org_id,
        from_currency=from_currency,
        to_currency=to_currency,
        company_id=company_id,
        limit=limit,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/exchange-rates/lookup/{from_currency}")
def resolve_exchange_rate(
    from_currency: str,
    context=Depends(require_fx_read),
    rate_date: str = Query(...),
    to_currency: str = Query(default="INR"),
    company_id: str | None = Query(default=None),
) -> dict:
    try:
        item = exchange_rate_service.resolve_rate(
            context.org_id,
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            company_id=company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/exchange-rates/{rate_id}")
def get_exchange_rate(rate_id: str, context=Depends(require_fx_read)) -> dict:
    try:
        item = exchange_rate_service.get_rate(context.org_id, rate_id=rate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/exchange-rates/{rate_id}")
def update_exchange_rate(
    rate_id: str, request: ExchangeRateUpdateRequest, context=Depends(require_fx_admin)
) -> dict:
    try:
        item = exchange_rate_service.update_rate(
            context.org_id, rate_id=rate_id, rate=request.rate, source=request.source
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.delete("/exchange-rates/{rate_id}")
def delete_exchange_rate(rate_id: str, context=Depends(require_fx_admin)) -> dict:
    try:
        item = exchange_rate_service.delete_rate(context.org_id, rate_id=rate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/revaluation-runs")
def run_fx_revaluation(request: FxRevaluationRunRequest, context=Depends(require_fx_admin)) -> dict:
    try:
        item = fx_revaluation_service.run_revaluation(
            context.org_id,
            revaluation_date=request.revaluation_date,
            company_id=request.company_id,
            fiscal_period_id=request.fiscal_period_id,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/revaluation-runs")
def list_fx_revaluation_runs(
    context=Depends(require_fx_read), limit: int = Query(default=50, ge=1, le=200)
) -> dict:
    items = fx_revaluation_service.list_runs(context.org_id, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/revaluation-runs/{run_id}")
def get_fx_revaluation_run(run_id: str, context=Depends(require_fx_read)) -> dict:
    try:
        item = fx_revaluation_service.get_run(context.org_id, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
