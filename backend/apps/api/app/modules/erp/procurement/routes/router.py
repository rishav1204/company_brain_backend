from fastapi import APIRouter

from app.modules.erp.procurement.routes import (
    analytics_routes,
    grn_routes,
    matching_routes,
    purchase_order_routes,
    requisition_routes,
)

erp_procurement_router = APIRouter(prefix="/erp/procurement", tags=["erp-procurement"])
erp_procurement_router.include_router(requisition_routes.router)
erp_procurement_router.include_router(purchase_order_routes.router)
erp_procurement_router.include_router(grn_routes.router)
erp_procurement_router.include_router(matching_routes.router)
erp_procurement_router.include_router(analytics_routes.router)
