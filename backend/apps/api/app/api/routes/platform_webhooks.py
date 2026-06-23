from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.platform.events.services.webhook_service import webhook_service
from app.modules.platform.integrations.security.url_safety import UnsafeUrlError, validate_outbound_url


router = APIRouter(tags=["platform-webhooks"])


class WebhookSubscriptionCreate(BaseModel):
    name: str
    target_url: str
    secret: str
    event_types: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 60


@router.post("/webhooks/subscriptions")
def create_webhook_subscription(request: WebhookSubscriptionCreate, context=Depends(build_request_context)) -> dict:
    if not webhook_service.schema_ready():
        raise HTTPException(status_code=503, detail="Webhook schema not ready — run migration 015")
    try:
        target_url = validate_outbound_url(request.target_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = webhook_service.create_subscription(
        org_id=context.org_id,
        name=request.name,
        target_url=target_url,
        secret=request.secret,
        event_types=request.event_types,
        rate_limit_per_minute=request.rate_limit_per_minute,
    )
    return {"request_id": context.request_id, "subscription": row, "verification_status": "created"}


@router.get("/webhooks/subscriptions")
def list_webhook_subscriptions(context=Depends(build_request_context)) -> dict:
    if not webhook_service.schema_ready():
        return {"request_id": context.request_id, "items": [], "verification_status": "schema_not_ready"}
    items = webhook_service.list_subscriptions(context.org_id)
    return {"request_id": context.request_id, "items": items, "verification_status": "verified"}


@router.post("/webhooks/deliveries/process")
def process_webhook_deliveries(context=Depends(build_request_context)) -> dict:
    count = webhook_service.process_pending_deliveries(context.org_id)
    return {"request_id": context.request_id, "processed": count, "verification_status": "deliveries_processed"}
