from fastapi import APIRouter

from app.modules.finance_os.forecasting.routes import (
    cash_forecast_routes,
    collections_forecast_routes,
    expense_forecast_routes,
    forecast_dashboard_routes,
    scenario_routes,
    tax_forecast_routes,
    working_capital_routes,
)

router = APIRouter(prefix="/finance-os/forecasting")
router.include_router(cash_forecast_routes.router)
router.include_router(collections_forecast_routes.router)
router.include_router(expense_forecast_routes.router)
router.include_router(tax_forecast_routes.router)
router.include_router(working_capital_routes.router)
router.include_router(scenario_routes.router)
router.include_router(forecast_dashboard_routes.router)

__all__ = ["router"]

