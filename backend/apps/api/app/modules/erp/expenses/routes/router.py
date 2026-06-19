from fastapi import APIRouter

from app.modules.erp.expenses.routes import (
    advance_routes,
    analytics_routes,
    claim_routes,
    policy_routes,
    receipt_routes,
    reimbursement_routes,
)

erp_expenses_router = APIRouter(prefix="/erp/expenses", tags=["erp-expenses"])
erp_expenses_router.include_router(claim_routes.router)
erp_expenses_router.include_router(receipt_routes.router)
erp_expenses_router.include_router(reimbursement_routes.router)
erp_expenses_router.include_router(policy_routes.router)
erp_expenses_router.include_router(advance_routes.router)
erp_expenses_router.include_router(analytics_routes.router)
