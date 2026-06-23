from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository
from app.modules.platform.integrations.security.credential_manager import credential_manager
from app.modules.platform.integrations.security.signature_validator import verify_hmac_sha256
from app.modules.platform.integrations.services.ingestion_service import ingestion_service
from app.services.event_bus import event_bus
from app.services.rate_limiter import FixedWindowRateLimiter

router = APIRouter()
_inbound_webhook_limiter = FixedWindowRateLimiter(limit_per_minute=120)


@router.post("/webhooks/inbound/{org_id}/{subscription_id}")
async def inbound_webhook(
    org_id: str,
    subscription_id: str,
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
) -> dict:
    """
    Inbound webhook receiver for external systems posting into our platform.

    Security:
    - Require HMAC signature header `X-Webhook-Signature`
    - Resolve secret from `integrations.webhook_subscriptions.secret_encrypted`
    """
    raw = await request.body()
    client_ip = request.client.host if request.client else "unknown"
    limit_key = f"inbound-webhook:{org_id}:{client_ip}"
    if not _inbound_webhook_limiter.check(limit_key).allowed:
        raise HTTPException(status_code=429, detail="Too many webhook requests")

    subs = webhook_repository.list_subscriptions_with_secrets(org_id)
    sub = next((s for s in subs if str(s.get("id")) == subscription_id), None)
    if not sub:
        raise HTTPException(status_code=401, detail="Unauthorized")
    secret_plain = ""
    if sub.get("secret_encrypted"):
        try:
            secret_plain = str(credential_manager.decrypt_json(str(sub["secret_encrypted"])).get("secret") or "")
        except Exception:
            secret_plain = ""
    if not verify_hmac_sha256(secret=secret_plain, payload=raw, signature_hex=x_webhook_signature or ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload: dict = {}
    try:
        payload = json.loads(raw.decode())
    except Exception:
        payload = {"raw": raw.decode(errors="ignore")}

    ingestion = ingestion_service.create(
        org_id,
        source_type="webhook",
        source_reference=f"subscription:{subscription_id}",
        payload=payload,
    )
    # Emit canonical event so workflows/automation can react.
    event_bus.publish(
        event_type="webhook.received",
        org_id=org_id,
        source="integrations",
        trace_id="",
        entity_type="integration_webhook",
        entity_id=str(ingestion.get("id") or ""),
        payload={
            "org_id": org_id,
            "subscription_id": subscription_id,
            "ingestion_record_id": ingestion.get("id"),
            "payload": payload,
        },
    )
    try:
        from app.modules.platform.governance.services.audit_service import audit_service
        from app.modules.platform.governance.utils.object_ref import format_object_ref

        audit_service.record(
            org_id=org_id,
            actor_type="system",
            actor_id="integrations.inbound",
            action="webhook.received",
            object_ref=format_object_ref("integrations", "ingestion_record", str(ingestion.get("id") or "")),
            payload={"subscription_id": subscription_id},
            entity_type="ingestion_record",
            entity_id=str(ingestion.get("id") or ""),
            source_service="api_gateway",
        )
    except Exception:
        pass
    return {"status": "ok", "ingestion_record_id": ingestion.get("id")}

