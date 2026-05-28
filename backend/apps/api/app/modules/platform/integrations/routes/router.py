from fastapi import APIRouter

from app.modules.platform.integrations.routes import (
    api_key_routes,
    connector_routes,
    inbound_webhook_routes,
    ingestion_routes,
    registry_routes,
    ops_routes,
    sync_routes,
    webhook_routes,
    webhook_delivery_routes,
)

integrations_router = APIRouter(prefix="/integrations", tags=["integrations"])
integrations_router.include_router(connector_routes.router)
integrations_router.include_router(webhook_routes.router)
integrations_router.include_router(sync_routes.router)
integrations_router.include_router(api_key_routes.router)
integrations_router.include_router(ingestion_routes.router)
integrations_router.include_router(registry_routes.router)
integrations_router.include_router(inbound_webhook_routes.router)
integrations_router.include_router(ops_routes.router)
integrations_router.include_router(webhook_delivery_routes.router)

