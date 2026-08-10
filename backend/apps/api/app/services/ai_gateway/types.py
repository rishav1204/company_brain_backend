"""Shared types for AI Gateway (Wave 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionClass(str, Enum):
    """Deterministic routing of work — never over-spend for simple tasks."""

    NO_AI = "no_ai"
    DETERMINISTIC_TOOL = "deterministic_tool"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    PLANNING = "planning"
    AGENTIC_WORKFLOW = "agentic_workflow"
    LONG_RUNNING_GOAL = "long_running_goal"
    INTENT_CLASSIFY = "intent_classify"
    EMBEDDING = "embedding"
    OCR_VISION = "ocr_vision"
    ANSWER = "answer"


@dataclass
class GatewayRequest:
    org_id: str
    system_prompt: str
    user_prompt: str
    estimated_tokens: int = 1500
    operation_code: str | None = None
    usage_operation_code: str | None = None
    execution_class: ExecutionClass | str | None = None
    intent: str | None = None
    complexity: float | None = None  # 0..1
    require_json: bool = False
    user_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    model_override: str | None = None
    max_output_tokens: int | None = None
    temperature: float = 0.2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayDecision:
    execution_class: ExecutionClass
    selected_model: str
    provider: str
    reason: str
    skip_llm: bool = False
    prefer_cache: bool = True
    prefer_deterministic: bool = False
    context_budget_tokens: int = 8000
    estimated_cost_usd: float = 0.0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    optimizations: list[str] = field(default_factory=list)
    fallback_models: list[str] = field(default_factory=list)


@dataclass
class GatewayResult:
    text: str
    decision: GatewayDecision
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cache_hit: bool = False
    model: str = ""
    provider: str = "openai"
    governance: dict[str, Any] = field(default_factory=dict)
    from_cache: bool = False


def as_execution_class(value: ExecutionClass | str | None) -> ExecutionClass | None:
    if value is None:
        return None
    if isinstance(value, ExecutionClass):
        return value
    try:
        return ExecutionClass(str(value))
    except ValueError:
        return None
