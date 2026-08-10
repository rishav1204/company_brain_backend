"""Context budget engine — per-request token window allocation (Wave 6)."""

from __future__ import annotations

from app.core.config import settings
from app.services.ai_gateway.types import ExecutionClass


# Model context windows (chars not exact — used as token proxy)
_MODEL_WINDOWS: dict[str, int] = {
    "gpt-4.1": 128_000,
    "gpt-4.1-mini": 128_000,
    "default": 32_000,
}


class ContextBudgetEngine:
    def model_window(self, model: str) -> int:
        return int(_MODEL_WINDOWS.get(model) or _MODEL_WINDOWS["default"])

    def budget_for(
        self,
        execution_class: ExecutionClass,
        *,
        model: str,
        estimated_tokens: int,
        conversation_tokens: int = 0,
        working_memory_tokens: int = 0,
        plan_soft: bool = False,
    ) -> int:
        """Tokens allowed for prompts (system+user) for this call."""
        window = self.model_window(model)
        # Reserve output + safety
        class_cap = {
            ExecutionClass.INTENT_CLASSIFY: 1_500,
            ExecutionClass.EMBEDDING: 8_000,
            ExecutionClass.RETRIEVAL: 4_000,
            ExecutionClass.ANSWER: 8_000,
            ExecutionClass.REASONING: 10_000,
            ExecutionClass.PLANNING: 6_000,
            ExecutionClass.AGENTIC_WORKFLOW: 6_000,
            ExecutionClass.LONG_RUNNING_GOAL: 8_000,
            ExecutionClass.OCR_VISION: 6_000,
            ExecutionClass.DETERMINISTIC_TOOL: 500,
            ExecutionClass.NO_AI: 0,
        }.get(execution_class, 8_000)

        configured = int(getattr(settings, "ai_default_context_budget_tokens", 8000) or 8000)
        max_ctx = int(getattr(settings, "m38_max_context_chars", 24000) or 24000) // 4

        budget = min(class_cap, configured, max_ctx, max(500, window // 4))
        # Leave room for estimated completion
        output_reserve = min(2_000, max(300, estimated_tokens // 3))
        budget = max(300, budget - output_reserve)

        # Soft plan mode shrinks
        if plan_soft:
            budget = int(budget * 0.6)

        # Already large conversation → shrink incoming
        overhead = conversation_tokens + working_memory_tokens
        if overhead > budget // 2:
            budget = max(400, budget - overhead // 2)

        return budget

    def compressor_budget(self, execution_class: ExecutionClass, *, model: str) -> int:
        return self.budget_for(execution_class, model=model, estimated_tokens=800)


context_budget_engine = ContextBudgetEngine()
