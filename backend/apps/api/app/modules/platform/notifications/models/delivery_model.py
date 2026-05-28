from dataclasses import dataclass


@dataclass
class DeliveryLogRecord:
    id: str
    notification_id: str
    provider: str
    delivery_status: str
    attempt_count: int
