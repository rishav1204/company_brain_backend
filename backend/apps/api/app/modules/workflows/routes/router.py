from fastapi import APIRouter

from app.modules.workflows.routes import (
    approval_routes,
    audit_routes,
    definition_routes,
    escalation_routes,
    realtime_routes,
    step_routes,
    task_routes,
    workflow_routes,
)

router = APIRouter()
router.include_router(definition_routes.router)
router.include_router(realtime_routes.router)
router.include_router(audit_routes.router)
router.include_router(step_routes.router)
router.include_router(workflow_routes.router)
router.include_router(approval_routes.router)
router.include_router(task_routes.router)
router.include_router(escalation_routes.router)
