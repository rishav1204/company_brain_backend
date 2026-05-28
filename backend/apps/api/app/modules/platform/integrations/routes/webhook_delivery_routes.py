from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.platform.integrations.repositories.webhook_delivery_repository import webhook_delivery_repository
from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository
from app.modules.platform.integrations.security.credential_manager import credential_manager
from app.modules.platform.integrations.services.webhook_service import sign_payload
from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service

router = APIRouter()


@router.get("/webhooks/deliveries")
def list_deliveries(
    context=Depends(build_request_context),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
) -> dict:
    items = webhook_delivery_repository.list_deliveries(context.org_id, limit=limit, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/webhooks/deliveries/{delivery_id}")
def get_delivery(delivery_id: str, context=Depends(build_request_context)) -> dict:
    item = webhook_delivery_repository.get_delivery(context.org_id, delivery_id=delivery_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/webhooks/deliveries/{delivery_id}/replay")
def replay_delivery(delivery_id: str, context=Depends(build_request_context)) -> dict:
    delivery = webhook_delivery_repository.get_delivery(context.org_id, delivery_id=delivery_id)
    if not delivery:
        return {"request_id": context.request_id, "error": "delivery_not_found"}

    # Resolve subscription secret and re-send exactly the same envelope payload.
    subs = webhook_repository.list_subscriptions_with_secrets(context.org_id)
    sub = next((s for s in subs if str(s.get("id")) == str(delivery.get("subscription_id"))), None)
    if not sub:
        return {"request_id": context.request_id, "error": "subscription_not_found"}

    secret_plain = ""
    if sub.get("secret_encrypted"):
        secret_plain = str(credential_manager.decrypt_json(str(sub["secret_encrypted"])).get("secret") or "")
    if not secret_plain:
        return {"request_id": context.request_id, "error": "secret_unavailable"}

    envelope = delivery.get("payload") or {}
    body = json.dumps({"event_type": delivery.get("event_type"), "envelope": envelope}, default=str).encode()
    signature = sign_payload(secret_plain, body)
    integrations_webhook_service._deliver_now(  # noqa: SLF001
        context.org_id,
        delivery_id=str(delivery_id),
        target_url=str(sub.get("endpoint_url")),
        body=body,
        signature=signature,
        event_type=str(delivery.get("event_type")),
    )
    return {"request_id": context.request_id, "replayed": True}

