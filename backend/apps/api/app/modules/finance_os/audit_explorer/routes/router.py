from fastapi import APIRouter

from app.modules.finance_os.audit_explorer.routes import (
    audit_routes,
    timeline_routes,
    evidence_routes,
    ai_audit_routes,
    workflow_audit_routes,
    copilot_routes,
)

router = APIRouter(prefix="/finance-os/audit")
router.include_router(timeline_routes.router)
router.include_router(evidence_routes.router)
router.include_router(ai_audit_routes.router)
router.include_router(workflow_audit_routes.router)
router.include_router(audit_routes.router)
router.include_router(copilot_routes.router)

__all__ = ["router"]
