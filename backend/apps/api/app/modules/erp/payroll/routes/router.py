from fastapi import APIRouter

from app.modules.erp.payroll.routes import payroll_routes

erp_payroll_router = APIRouter(prefix="/erp/payroll", tags=["erp-payroll"])
erp_payroll_router.include_router(payroll_routes.router)
