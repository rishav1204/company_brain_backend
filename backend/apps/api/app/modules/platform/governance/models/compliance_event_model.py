from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ComplianceEventRecord:
    id: str
    org_id: str
    compliance_type: str
    status: str
    severity: str
    related_entity_type: str | None
    related_entity_id: str | None
    details: dict[str, Any]
    created_at: str | None = None
