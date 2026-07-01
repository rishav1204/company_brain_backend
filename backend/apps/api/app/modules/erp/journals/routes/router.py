from fastapi import APIRouter

from app.modules.erp.journals.routes import accrual_routes
from app.modules.erp.journals.routes import journal_routes
from app.modules.erp.journals.routes import posting_routes
from app.modules.erp.journals.routes import recurring_routes
from app.modules.erp.journals.routes import reversal_routes

erp_journals_router = APIRouter(prefix="/erp", tags=["erp-journals"])
# Static /journals/* paths must register before /journals/{journal_id} or FastAPI
# treats segments like "recurring" and "approval-queue" as journal IDs.
erp_journals_router.include_router(recurring_routes.router)
erp_journals_router.include_router(posting_routes.router)
erp_journals_router.include_router(journal_routes.router)
erp_journals_router.include_router(reversal_routes.router)
erp_journals_router.include_router(accrual_routes.router)
