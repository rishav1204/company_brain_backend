from dataclasses import dataclass


@dataclass
class NotificationRecord:
    id: str
    org_id: str
    notification_type: str
    channel: str
    status: str
    priority: str
    body: str
    subject: str | None = None
