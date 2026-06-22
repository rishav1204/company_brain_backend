from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.forecasting.security.forecasting_guard import require_forecasting_read
from app.modules.finance_os.forecasting.services.forecast_query_service import get_series
from app.modules.finance_os.forecasting.schemas.forecasting_schema import ForecastSeriesResponse
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-forecasting"])


@router.get("/expenses", response_model=ForecastSeriesResponse)
def expense_forecast(horizon_days: int = 30, as_of_date: str | None = None, context=Depends(build_request_context)) -> ForecastSeriesResponse:
    require_forecasting_read(context.user)
    data = get_series(context.org_id, forecast_type="expenses", horizon_days=horizon_days, as_of_date=as_of_date)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="forecast.expenses.read",
        object_ref=f"forecast:expenses:{horizon_days}",
    )
    return ForecastSeriesResponse(
        forecast_type="expenses",
        horizon_days=horizon_days,
        as_of_date=data["as_of_date"] or (as_of_date or ""),
        confidence_score=data["confidence_score"],
        confidence_band=data["confidence_band"],
        items=data["items"],
        explanation=data.get("explanation"),
        evidence=data.get("evidence") or {},
    )

