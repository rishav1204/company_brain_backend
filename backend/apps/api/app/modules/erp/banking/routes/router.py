from fastapi import APIRouter

from app.modules.erp.banking.routes import banking_routes

erp_m22_banking_router = APIRouter(prefix="/erp/banking", tags=["erp-banking-m22"])
erp_m22_banking_router.include_router(banking_routes.router)

legacy_banking_router = APIRouter(prefix="/banking", tags=["erp-banking-legacy"])
legacy_banking_router.include_router(banking_routes.router)
