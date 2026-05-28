from fastapi import APIRouter

from app.modules.erp.coa.routes import (
    account_routes,
    coa_routes,
    cost_center_routes,
    group_routes,
    import_export_routes,
    mapping_routes,
)

erp_coa_router = APIRouter(prefix="/erp", tags=["erp-coa"])
erp_coa_router.include_router(group_routes.router)
erp_coa_router.include_router(account_routes.router)
erp_coa_router.include_router(cost_center_routes.router)
erp_coa_router.include_router(mapping_routes.router)
erp_coa_router.include_router(coa_routes.router)
erp_coa_router.include_router(import_export_routes.router)

