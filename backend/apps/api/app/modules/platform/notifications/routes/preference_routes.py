from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.platform.notifications.services.preference_service import preference_service

router = APIRouter(tags=["notification-preferences"])


class PreferenceUpsert(BaseModel):
    channel: str
    notification_type: str
    enabled: bool = True
    quiet_hours: dict = Field(default_factory=dict)


@router.get("/preferences")
def list_preferences(context=Depends(build_request_context)) -> dict:
    return {"request_id": context.request_id, "items": preference_service.list(context.org_id, context.user_id)}


@router.post("/preferences")
def upsert_preference(request: PreferenceUpsert, context=Depends(build_request_context)) -> dict:
    row = preference_service.upsert(
        context.org_id,
        user_id=context.user_id,
        channel=request.channel,
        notification_type=request.notification_type,
        enabled=request.enabled,
        quiet_hours=request.quiet_hours,
    )
    return {"request_id": context.request_id, "preference": row}
