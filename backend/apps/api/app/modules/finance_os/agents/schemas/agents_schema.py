from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    org_id: str
    agent_name: str
    task_type: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    memory_snippets: list[dict] = field(default_factory=list)
    graph_paths: list[dict] = field(default_factory=list)
    erp_facts: dict = field(default_factory=dict)
    policy_flags: list[str] = field(default_factory=list)
    data_quality_score: float = 0.0
    raw_payload: dict = field(default_factory=dict)


@dataclass
class AgentPlan:
    agent_name: str
    task_type: str
    recommendation_type: str
    recommendation: str
    proposed_actions: list[dict] = field(default_factory=list)
    workflow_key: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentRunRequest:
    agent_type: str
    trigger_type: str = "api"
    payload: dict = field(default_factory=dict)


@dataclass
class ConfidenceResult:
    score: float
    band: str
    approval_required: bool
    factors: dict = field(default_factory=dict)
