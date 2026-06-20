from fastapi import APIRouter

from app.modules.finance_os.workflow_intelligence.routes import (
    analytics_routes,
    bottleneck_routes,
    optimization_routes,
    sla_routes,
    workflow_ai_routes,
)

router = APIRouter(prefix="/finance-os/workflow-intelligence")
router.include_router(workflow_ai_routes.router)
router.include_router(bottleneck_routes.router)
router.include_router(sla_routes.router)
router.include_router(optimization_routes.router)
router.include_router(analytics_routes.router)

__all__ = ["router"]
