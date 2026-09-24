from fastapi import APIRouter

from app.modules.erp.gl.routes import balance_routes
from app.modules.erp.gl.routes import fiscal_period_routes
from app.modules.erp.gl.routes import ledger_routes
from app.modules.erp.gl.routes import parallel_ledger_routes
from app.modules.erp.gl.routes import posting_routes
from app.modules.erp.gl.routes import reversal_routes
from app.modules.erp.gl.routes import trial_balance_routes

erp_gl_router = APIRouter(prefix="/erp", tags=["erp-gl"])
erp_gl_router.include_router(posting_routes.router)
erp_gl_router.include_router(balance_routes.router)
erp_gl_router.include_router(trial_balance_routes.router)
erp_gl_router.include_router(ledger_routes.router)
erp_gl_router.include_router(reversal_routes.router)
erp_gl_router.include_router(parallel_ledger_routes.router)
# FE compatibility alias — canonical periods live at /erp/ledger/periods
erp_gl_router.include_router(fiscal_period_routes.router)

