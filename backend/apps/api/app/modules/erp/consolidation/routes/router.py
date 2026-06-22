from fastapi import APIRouter

from app.modules.erp.consolidation.routes import (
    branch_routes,
    consolidation_routes,
    elimination_routes,
    entity_routes,
    intercompany_routes,
)

router = APIRouter(prefix="/erp/consolidation")
router.include_router(entity_routes.router)
router.include_router(branch_routes.router)
router.include_router(intercompany_routes.router)
router.include_router(consolidation_routes.router)
router.include_router(elimination_routes.router)

__all__ = ["router"]
