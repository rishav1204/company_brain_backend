from __future__ import annotations

from typing import Any, TypedDict


class WorkflowDefinition(TypedDict, total=False):
    id: str
    org_id: str
    workflow_key: str
    name: str
    version: int
    is_active: bool
    definition_json: dict[str, Any]


class WorkflowInstance(TypedDict, total=False):
    id: str
    org_id: str
    workflow_type: str
    status: str
    priority: str
    started_by: str
    metadata: dict[str, Any]
