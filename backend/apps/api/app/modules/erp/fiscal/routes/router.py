from fastapi import APIRouter

from app.modules.erp.fiscal.routes import (
    close_routes,
    fiscal_period_routes,
    fiscal_year_routes,
    reopen_routes,
    year_end_routes,
)

erp_fiscal_router = APIRouter(prefix="/erp/ledger", tags=["erp-fiscal"])
erp_fiscal_router.include_router(fiscal_year_routes.router)
erp_fiscal_router.include_router(fiscal_period_routes.router)
erp_fiscal_router.include_router(close_routes.router)
erp_fiscal_router.include_router(reopen_routes.router)
erp_fiscal_router.include_router(year_end_routes.router)
