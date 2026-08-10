from fastapi import APIRouter

from app.modules.erp.treasury.routes import cash_position_routes, dashboard_routes, forecast_routes, transfer_routes

erp_m24_treasury_router = APIRouter(prefix="/erp/treasury", tags=["erp-treasury-m24"])
erp_m24_treasury_router.include_router(cash_position_routes.router)
erp_m24_treasury_router.include_router(transfer_routes.router)
erp_m24_treasury_router.include_router(dashboard_routes.router)
erp_m24_treasury_router.include_router(forecast_routes.router)

legacy_treasury_router = APIRouter(prefix="/treasury", tags=["erp-treasury-legacy"])
legacy_treasury_router.include_router(cash_position_routes.router)
legacy_treasury_router.include_router(transfer_routes.router)
legacy_treasury_router.include_router(dashboard_routes.router)
legacy_treasury_router.include_router(forecast_routes.router)

# Wave 4: canonical name must point at /erp/treasury router (was accidentally aliasing legacy).
# legacy_treasury_router remains unmounted — keep for optional BC window docs only.
erp_treasury_router = erp_m24_treasury_router
