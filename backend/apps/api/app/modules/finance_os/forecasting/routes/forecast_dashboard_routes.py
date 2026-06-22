from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.forecasting.repositories.forecast_repository import forecast_repository
from app.modules.finance_os.forecasting.security.forecasting_guard import require_forecasting_read
from app.modules.finance_os.forecasting.schemas.forecasting_schema import DashboardResponse
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-forecasting"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(context=Depends(build_request_context)) -> DashboardResponse:
    require_forecasting_read(context.user)
    as_of_cash = forecast_repository.distinct_latest_as_of(context.org_id, forecast_type="cash") or ""
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="forecast.dashboard.read",
        object_ref="forecast:dashboard",
    )
    return DashboardResponse(
        as_of_date=as_of_cash,
        cash={"as_of_date": as_of_cash},
        collections={"as_of_date": forecast_repository.distinct_latest_as_of(context.org_id, forecast_type="collections") or ""},
        expenses={"as_of_date": forecast_repository.distinct_latest_as_of(context.org_id, forecast_type="expenses") or ""},
        tax={"as_of_date": forecast_repository.distinct_latest_as_of(context.org_id, forecast_type="tax") or ""},
        working_capital={"as_of_date": forecast_repository.distinct_latest_as_of(context.org_id, forecast_type="working_capital") or ""},
    )

