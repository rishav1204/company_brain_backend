from __future__ import annotations

from typing import TypedDict


class Approval(TypedDict, total=False):
    id: str
    workflow_instance_id: str
    workflow_step_id: str
    decision: str
    level: int
    approver_user_id: str
