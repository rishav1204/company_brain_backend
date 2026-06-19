from fastapi import APIRouter

from app.modules.erp.reconciliation.routes import reconciliation_routes

erp_m23_reconciliation_router = APIRouter(prefix="/erp/reconciliation", tags=["erp-reconciliation-m23"])
erp_m23_reconciliation_router.include_router(reconciliation_routes.router)

legacy_reconciliation_alias = APIRouter(prefix="/banking/reconciliation", tags=["erp-reconciliation-legacy"])
legacy_reconciliation_alias.include_router(reconciliation_routes.router)
