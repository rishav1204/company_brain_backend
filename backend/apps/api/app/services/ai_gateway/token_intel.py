"""Token intelligence + cost calculation (Wave 6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.ai_gateway.model_router import model_router
from app.services.logger import log_event


@dataclass
class TokenTelemetry:
    org_id: str
    provider: str
    model: str
    operation_code: str | None
    execution_class: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_tokens: int
    cost_usd: float
    latency_ms: float
    cache_hit: bool
    user_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    routing_reason: str = ""
    optimizations: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenIntelligence:
    def build(
        self,
        *,
        org_id: str,
        provider: str,
        model: str,
        operation_code: str | None,
        execution_class: str,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_tokens: int,
        latency_ms: float,
        cache_hit: bool = False,
        user_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        routing_reason: str = "",
        optimizations: list[str] | None = None,
        estimated_cost_usd: float = 0.0,
    ) -> TokenTelemetry:
        cost = model_router.estimate_cost_usd(model, input_tokens=prompt_tokens, output_tokens=completion_tokens)
        return TokenTelemetry(
            org_id=org_id,
            provider=provider,
            model=model,
            operation_code=operation_code,
            execution_class=execution_class,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_tokens=estimated_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            user_id=user_id,
            goal_id=goal_id,
            workflow_id=workflow_id,
            routing_reason=routing_reason,
            optimizations=list(optimizations or []),
            estimated_cost_usd=estimated_cost_usd,
        )

    def persist_usage(self, tel: TokenTelemetry, *, credits_charged: float = 0.0) -> None:
        log_event(
            "ai.gateway.call",
            org_id=tel.org_id,
            model=tel.model,
            provider=tel.provider,
            operation_code=tel.operation_code or "",
            execution_class=tel.execution_class,
            prompt_tokens=tel.prompt_tokens,
            completion_tokens=tel.completion_tokens,
            total_tokens=tel.total_tokens,
            cost_usd=tel.cost_usd,
            latency_ms=tel.latency_ms,
            cache_hit=tel.cache_hit,
            goal_id=tel.goal_id or "",
            user_id=tel.user_id or "",
            routing_reason=(tel.routing_reason or "")[:200],
        )
        try:
            from app.modules.platform.billing.services.credit_service import credit_service

            credit_service.log_ai_usage(
                tel.org_id,
                provider=tel.provider,
                model=tel.model,
                operation_code=tel.operation_code,
                prompt_tokens=tel.prompt_tokens,
                completion_tokens=tel.completion_tokens,
                cost_usd=tel.cost_usd,
                credits_charged=credits_charged,
                metadata=tel.to_dict(),
                reference_type="goal" if tel.goal_id else None,
                reference_id=tel.goal_id,
            )
        except Exception:
            pass


token_intelligence = TokenIntelligence()
