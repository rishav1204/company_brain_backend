from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GovernanceViolation:
    id: str
    org_id: str
    violation_type: str
    severity: str
    detected_by: str
    details: dict[str, Any]
    entity_type: str | None = None
    entity_id: str | None = None
    resolved: bool = False
