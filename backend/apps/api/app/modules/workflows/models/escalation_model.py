from __future__ import annotations

from typing import TypedDict


class Escalation(TypedDict, total=False):
    id: str
    workflow_instance_id: str
    escalation_type: str
    escalated_to: str
