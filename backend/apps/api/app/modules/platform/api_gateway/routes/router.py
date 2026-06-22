from __future__ import annotations

from fastapi import APIRouter

from app.modules.platform.api_gateway.routes import (
    api_keys_routes,
    event_routes,
    integration_health_routes,
    subscription_routes,
    webhook_routes,
)

api_gateway_router = APIRouter(prefix="/platform", tags=["platform-api-gateway"])
api_gateway_router.include_router(api_keys_routes.router)
api_gateway_router.include_router(webhook_routes.router)
api_gateway_router.include_router(subscription_routes.router)
api_gateway_router.include_router(event_routes.router)
api_gateway_router.include_router(integration_health_routes.router)
