from fastapi import APIRouter

from app.modules.finance_os.agents.routes import agent_routes, shortcut_routes

router = APIRouter(prefix="/finance-os/agents")
router.include_router(agent_routes.router)
router.include_router(shortcut_routes.router)

__all__ = ["router"]
