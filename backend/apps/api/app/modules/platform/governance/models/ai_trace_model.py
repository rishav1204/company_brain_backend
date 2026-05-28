from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AIReasoningTrace:
    id: str
    org_id: str
    prompt_hash: str
    reasoning_summary: str
    confidence_score: float | None
    decision: dict[str, Any]
    agent_run_id: str | None = None
    workflow_id: str | None = None
    retrieved_context: dict[str, Any] | None = None
