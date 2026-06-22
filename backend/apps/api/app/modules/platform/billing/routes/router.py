from fastapi import APIRouter

from app.modules.platform.billing.routes.billing_routes import router as billing_routes
from app.modules.platform.billing.routes.admin_billing_routes import router as admin_billing_routes

billing_router = APIRouter()
billing_router.include_router(billing_routes)
billing_router.include_router(admin_billing_routes)
