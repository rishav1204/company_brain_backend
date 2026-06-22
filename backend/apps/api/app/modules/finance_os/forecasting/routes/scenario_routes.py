from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.forecasting.engine.scenario_engine import DEFAULT_SCENARIOS
from app.modules.finance_os.forecasting.schemas.forecasting_schema import ScenarioResponse
from app.modules.finance_os.forecasting.security.forecasting_guard import require_forecasting_read
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-forecasting"])


@router.get("/scenarios", response_model=ScenarioResponse)
def scenarios(horizon_days: int = 90, as_of_date: str | None = None, context=Depends(build_request_context)) -> ScenarioResponse:
    require_forecasting_read(context.user)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="forecast.scenarios.read",
        object_ref=f"forecast:scenarios:{horizon_days}",
    )
    return ScenarioResponse(
        horizon_days=horizon_days,
        as_of_date=as_of_date or "",
        scenarios=[s.__dict__ for s in DEFAULT_SCENARIOS],
    )

