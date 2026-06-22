from fastapi import APIRouter

from app.modules.erp.compliance.routes import compliance_routes

erp_m21_compliance_router = APIRouter(prefix="/erp/compliance", tags=["erp-compliance-m21"])
erp_m21_compliance_router.include_router(compliance_routes.router)

# Blueprint alias: /api/v1/compliance/* → M21 compliance calendar (not tax compliance).
erp_compliance_alias_router = APIRouter(prefix="/compliance", tags=["erp-compliance-m21-alias"])
erp_compliance_alias_router.include_router(compliance_routes.router)
