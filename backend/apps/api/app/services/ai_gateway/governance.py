"""AI execution governance record (Wave 6)."""

from __future__ import annotations

from typing import Any

from app.services.ai_gateway.types import GatewayDecision, GatewayResult
from app.services.logger import log_event


class AIGovernance:
    def record(
        self,
        org_id: str,
        *,
        decision: GatewayDecision,
        result: GatewayResult | None = None,
        user_id: str | None = None,
        goal_id: str | None = None,
        blocked: bool = False,
        block_reason: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "estimated_cost_usd": decision.estimated_cost_usd,
            "actual_cost_usd": result.cost_usd if result else None,
            "estimated_tokens": decision.estimated_input_tokens + decision.estimated_output_tokens,
            "actual_prompt_tokens": result.prompt_tokens if result else None,
            "actual_completion_tokens": result.completion_tokens if result else None,
            "selected_model": decision.selected_model,
            "model_selection_reason": decision.reason,
            "context_budget": decision.context_budget_tokens,
            "cache_usage": bool(result and result.cache_hit) if result else False,
            "execution_class": decision.execution_class.value,
            "optimizations": decision.optimizations,
            "skip_llm": decision.skip_llm,
            "blocked": blocked,
            "block_reason": block_reason,
            "user_id": user_id,
            "goal_id": goal_id,
        }
        log_event("ai.gateway.governance", org_id=org_id, **{k: v for k, v in payload.items() if v is not None})
        try:
            from app.services.repositories import audit_repo

            audit_repo.create_log(
                org_id=org_id,
                actor_type="system",
                actor_id="ai_gateway",
                event_type="ai.gateway.execution",
                object_ref=f"goal:{goal_id or 'none'}",
                payload_jsonb=payload,
            )
        except Exception:
            pass
        return payload


ai_governance = AIGovernance()
