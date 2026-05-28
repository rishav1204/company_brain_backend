from dataclasses import dataclass
from datetime import datetime


@dataclass
class SessionRecord:
    id: str
    user_id: str
    org_id: str
    expires_at: datetime
    revoked: bool = False
