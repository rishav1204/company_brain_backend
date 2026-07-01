from fastapi import APIRouter

from app.modules.erp.assets.routes import (
    asset_routes,
    depreciation_routes,
    disposal_routes,
    impairment_routes,
    register_routes,
    transfer_routes,
)

erp_assets_router = APIRouter(prefix="/erp/assets", tags=["erp-assets"])
# Static paths (/register, /candidates, /analytics/*) must register before /{asset_id}.
erp_assets_router.include_router(register_routes.router)
erp_assets_router.include_router(asset_routes.router)
erp_assets_router.include_router(depreciation_routes.router)
erp_assets_router.include_router(transfer_routes.router)
erp_assets_router.include_router(disposal_routes.router)
erp_assets_router.include_router(impairment_routes.router)
