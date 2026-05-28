from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.schemas.webhook_schema import WebhookSubscriptionCreateRequest
from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service

router = APIRouter()


@router.post("/webhooks/subscriptions")
def create_webhook_subscription(request: WebhookSubscriptionCreateRequest, context=Depends(build_request_context)) -> dict:
    item, secret_plain = integrations_webhook_service.create_subscription(
        context.org_id,
        endpoint_url=request.endpoint_url,
        event_types=request.event_types,
    )
    # NOTE: return secret only once; frontend must store it.
    return {"request_id": context.request_id, "item": item, "secret": secret_plain}


@router.get("/webhooks/subscriptions")
def list_webhook_subscriptions(context=Depends(build_request_context)) -> dict:
    items = integrations_webhook_service.list_subscriptions(context.org_id)
    return {"request_id": context.request_id, "items": items}

