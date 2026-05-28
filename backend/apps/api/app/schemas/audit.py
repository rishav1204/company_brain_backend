from datetime import datetime
from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: str
    actor_type: str
    actor_id: str
    event_type: str
    object_ref: str
    payload_jsonb: dict
    created_at: datetime


class AuditLogListResponse(BaseModel):
    request_id: str
    items: list[AuditLogItem]
    confidence: float
    verification_status: str
