from fastapi import APIRouter

from app.modules.erp.vouchers.routes import typed_voucher_routes, voucher_routes

erp_vouchers_router = APIRouter(prefix="/erp", tags=["erp-vouchers"])
erp_vouchers_router.include_router(voucher_routes.router)
erp_vouchers_router.include_router(typed_voucher_routes.router)
