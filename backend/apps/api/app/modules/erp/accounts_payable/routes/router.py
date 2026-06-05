from fastapi import APIRouter

from app.modules.erp.accounts_payable.routes import aging_routes
from app.modules.erp.accounts_payable.routes import invoice_routes
from app.modules.erp.accounts_payable.routes import payment_routes
from app.modules.erp.accounts_payable.routes import statement_routes
from app.modules.erp.accounts_payable.routes import vendor_routes

erp_ap_router = APIRouter(prefix="/ap", tags=["erp-ap"])
erp_ap_router.include_router(vendor_routes.router)
erp_ap_router.include_router(invoice_routes.router)
erp_ap_router.include_router(payment_routes.router)
erp_ap_router.include_router(aging_routes.router)
erp_ap_router.include_router(statement_routes.router)
