from fastapi import APIRouter

from app.modules.finance_os.analytics.routes import (
    benchmark_routes,
    close_analytics_routes,
    collections_kpi_routes,
    compliance_kpi_routes,
    copilot_routes,
    executive_dashboard_routes,
    finance_kpi_routes,
    treasury_kpi_routes,
)

router = APIRouter(prefix="/finance-os/analytics")
router.include_router(executive_dashboard_routes.router)
router.include_router(finance_kpi_routes.router)
router.include_router(treasury_kpi_routes.router)
router.include_router(collections_kpi_routes.router)
router.include_router(compliance_kpi_routes.router)
router.include_router(close_analytics_routes.router)
router.include_router(benchmark_routes.router)
router.include_router(copilot_routes.router)

__all__ = ["router"]
