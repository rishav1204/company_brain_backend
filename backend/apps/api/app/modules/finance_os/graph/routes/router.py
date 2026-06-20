from fastapi import APIRouter

from app.modules.finance_os.graph.routes import (
    causality_routes,
    dependency_routes,
    graph_routes,
    lineage_routes,
    visualization_routes,
)

router = APIRouter(prefix="/finance-os/graph")
router.include_router(graph_routes.router)
router.include_router(lineage_routes.router)
router.include_router(dependency_routes.router)
router.include_router(causality_routes.router)
router.include_router(visualization_routes.router)

__all__ = ["router"]
