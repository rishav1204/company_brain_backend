from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StoredEvent:
    event_id: str
    event_type: str
    org_id: str
    source: str
    payload: dict[str, Any]
    status: str
    created_at: str | None = None
