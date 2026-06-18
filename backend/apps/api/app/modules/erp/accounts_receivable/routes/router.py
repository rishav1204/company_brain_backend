from fastapi import APIRouter

from app.modules.erp.accounts_receivable.routes import aging_routes
from app.modules.erp.accounts_receivable.routes import collection_routes
from app.modules.erp.accounts_receivable.routes import credit_routes
from app.modules.erp.accounts_receivable.routes import customer_routes
from app.modules.erp.accounts_receivable.routes import invoice_routes
from app.modules.erp.accounts_receivable.routes import statement_routes

erp_ar_router = APIRouter(prefix="/ar", tags=["erp-ar"])
erp_ar_router.include_router(customer_routes.router)
erp_ar_router.include_router(invoice_routes.router)
erp_ar_router.include_router(collection_routes.router)
erp_ar_router.include_router(aging_routes.router)
erp_ar_router.include_router(credit_routes.router)
erp_ar_router.include_router(statement_routes.router)
