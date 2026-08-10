from fastapi import APIRouter

from app.modules.erp.import_customs.routes import boe_routes

erp_import_customs_router = APIRouter(prefix="/erp/import-customs", tags=["erp-import-customs"])
erp_import_customs_router.include_router(boe_routes.router)
