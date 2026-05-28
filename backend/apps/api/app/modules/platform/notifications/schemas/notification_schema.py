from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: str
    notification_type: str
    channel: str
    subject: str | None = None
    body: str
    status: str
    priority: str = "medium"
