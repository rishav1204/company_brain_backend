from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.services.connector_registry import connector_registry
from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository
from app.modules.platform.events.queues.queue_manager import queue_manager

router = APIRouter()


@router.get("/integrations/health")
def integration_health(context=Depends(build_request_context)) -> dict:
    connectors = connector_registry.list()
    webhook_ready = webhook_repository.schema_ready()
    queue_lag = 0
    try:
        queue_lag = queue_manager.lag("integration.webhooks")
    except Exception:
        pass
    return {
        "request_id": context.request_id,
        "item": {
            "connectors": connectors,
            "webhooks_ready": webhook_ready,
            "webhook_queue_lag": queue_lag,
            "status": "healthy" if webhook_ready else "degraded",
        },
    }
