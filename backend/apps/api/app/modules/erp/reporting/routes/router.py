from fastapi import APIRouter

from app.modules.erp.reporting.routes import (
    aging_reports_routes,
    export_routes,
    financial_reports_routes,
    forecast_reports_routes,
    gst_reports_routes,
    tds_reports_routes,
    treasury_reports_routes,
)

router = APIRouter(prefix="/erp/reports")
router.include_router(financial_reports_routes.router)
router.include_router(aging_reports_routes.router)
router.include_router(gst_reports_routes.router)
router.include_router(tds_reports_routes.router)
router.include_router(treasury_reports_routes.router)
router.include_router(forecast_reports_routes.router)
router.include_router(export_routes.router)

__all__ = ["router"]
