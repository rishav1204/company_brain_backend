from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.api_gateway.engine.api_gateway_engine import api_gateway_engine
from app.modules.platform.api_gateway.schemas.gateway_schema import WebhookCreateRequest
from app.modules.platform.api_gateway.services.webhook_service import webhook_service

router = APIRouter()


@router.post("/webhooks")
def create_webhook(request: WebhookCreateRequest, context=Depends(build_request_context)) -> dict:
    def handler() -> dict:
        item, secret = webhook_service.create_subscription(
            context.org_id,
            endpoint_url=request.webhook_url,
            event_types=request.subscribed_events,
            name=request.name,
        )
        return {"request_id": context.request_id, "item": item, "secret_key": secret}

    return api_gateway_engine.process_external_request(
        context,
        action="webhook.subscribe",
        method="POST",
        path="/platform/webhooks",
        handler=handler,
        required_scopes=["webhooks.manage", "admin"],
    )


@router.get("/webhooks")
def list_webhooks(context=Depends(build_request_context)) -> dict:
    items = webhook_service.list_subscriptions(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.delete("/webhooks/{subscription_id}")
def delete_webhook(subscription_id: str, context=Depends(build_request_context)) -> dict:
    def handler() -> dict:
        item = webhook_service.deactivate(context.org_id, subscription_id=subscription_id)
        return {"request_id": context.request_id, "item": item}

    return api_gateway_engine.process_external_request(
        context,
        action="webhook.unsubscribe",
        method="DELETE",
        path=f"/platform/webhooks/{subscription_id}",
        handler=handler,
        required_scopes=["webhooks.manage", "admin"],
    )
