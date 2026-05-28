from __future__ import annotations

from typing import Any, TypedDict


class WorkflowStep(TypedDict, total=False):
    id: str
    step_key: str
    step_type: str
    status: str
    assigned_to: str
    due_at: Any
    retry_count: int
    metadata: dict[str, Any]
