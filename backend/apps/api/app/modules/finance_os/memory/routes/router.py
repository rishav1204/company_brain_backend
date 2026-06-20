from fastapi import APIRouter

from app.modules.finance_os.memory.routes import administration_routes, memory_routes, retrieval_routes

router = APIRouter(prefix="/finance-os/memory")
router.include_router(memory_routes.router)
router.include_router(retrieval_routes.router)
router.include_router(administration_routes.router)

__all__ = ["router"]
