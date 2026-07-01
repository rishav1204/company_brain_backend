from __future__ import annotations

from fastapi import APIRouter

from app.modules.finance_os.platform_ai_runtime.routes import runtime_routes
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import CopilotChatResponse

router = APIRouter(prefix="/finance-os/runtime")
router.include_router(runtime_routes.router)

copilot_router = APIRouter(prefix="/finance-os/copilot", tags=["finance-os-copilot"])
copilot_router.add_api_route(
    "/chat",
    runtime_routes.copilot_chat,
    methods=["POST"],
    response_model=CopilotChatResponse,
)
