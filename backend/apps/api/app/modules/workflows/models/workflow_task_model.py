from __future__ import annotations

from typing import Any, TypedDict


class WorkflowTask(TypedDict, total=False):
    id: str
    task_type: str
    status: str
    assigned_to: str
    payload: dict[str, Any]
