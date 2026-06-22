from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.api_gateway.routes import webhook_routes

router = APIRouter()
router.include_router(webhook_routes.router)
