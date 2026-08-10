from fastapi import APIRouter

from app.modules.erp.fx.routes import fx_routes

erp_fx_router = APIRouter(prefix="/erp/fx", tags=["erp-fx"])
erp_fx_router.include_router(fx_routes.router)
