from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyRule:
    id: str
    org_id: str
    policy_key: str
    policy_type: str
    conditions: dict[str, Any]
    actions: dict[str, Any]
    is_active: bool
    priority: int = 100
