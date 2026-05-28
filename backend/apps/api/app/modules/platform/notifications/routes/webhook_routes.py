from fastapi import APIRouter, Request

from app.services.logger import log_event

router = APIRouter(tags=["notification-webhooks"])


@router.post("/webhooks/notifications/resend")
async def resend_webhook(request: Request) -> dict:
    body = await request.json()
    log_event("notification.webhook.resend", payload_type=str(body.get("type", "")))
    return {"received": True}


@router.post("/webhooks/notifications/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    body = await request.json()
    log_event("notification.webhook.whatsapp", keys=list(body.keys())[:10])
    return {"received": True}
