"""Central AI Gateway — sole entry path for LLM invocations (Wave 6)."""

from __future__ import annotations

import time
from typing import Any, Callable

from app.core.config import settings
from app.core.prompt_sanitizer import sanitize_user_prompt
from app.services.ai_gateway.analytics import ai_usage_analytics
from app.services.ai_gateway.budget_manager import ai_budget_manager
from app.services.ai_gateway.context_budget import context_budget_engine
from app.services.ai_gateway.execution_classifier import execution_classifier
from app.services.ai_gateway.governance import ai_governance
from app.services.ai_gateway.model_router import model_router
from app.services.ai_gateway.prompt_cache import gateway_cache
from app.services.ai_gateway.prompt_optimizer import prompt_optimizer
from app.services.ai_gateway.token_intel import token_intelligence
from app.services.ai_gateway.types import (
    ExecutionClass,
    GatewayDecision,
    GatewayRequest,
    GatewayResult,
    as_execution_class,
)
from app.services.llm_runtime import llm_runtime_guard
from app.services.logger import log_event
from app.services.metrics import metrics_store


class AIBudgetExceededError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AIGateway:
    """Classifies → budgets → routes → optimizes → invokes provider callback → telemeters."""

    def plan(self, request: GatewayRequest) -> GatewayDecision:
        ec, reason, complexity = execution_classifier.classify(
            text=request.user_prompt,
            operation_code=request.operation_code or request.usage_operation_code,
            explicit=as_execution_class(request.execution_class),
            intent=request.intent,
            require_json=request.require_json,
        )
        complexity = request.complexity if request.complexity is not None else complexity

        est_in = prompt_optimizer.estimate_tokens(request.system_prompt) + prompt_optimizer.estimate_tokens(
            request.user_prompt
        )
        est_out = max(100, min(2000, request.estimated_tokens // 3))

        budget_status = ai_budget_manager.check(
            request.org_id,
            estimated_cost_usd=0.0,
            user_id=request.user_id,
            goal_id=request.goal_id,
        )
        prefer_cheap = budget_status.prefer_cheap

        model, provider, fallbacks, route_reason = model_router.resolve(
            ec,
            complexity=complexity,
            model_override=request.model_override,
            prefer_cheap=prefer_cheap,
            provider_health_ok=True,
        )
        ctx_budget = context_budget_engine.budget_for(
            ec,
            model=model,
            estimated_tokens=request.estimated_tokens,
            plan_soft=prefer_cheap,
        )
        est_cost = model_router.estimate_cost_usd(model, input_tokens=min(est_in, ctx_budget), output_tokens=est_out)

        # Re-check with estimated cost
        budget_status = ai_budget_manager.check(
            request.org_id,
            estimated_cost_usd=est_cost,
            user_id=request.user_id,
            goal_id=request.goal_id,
        )
        skip = False
        if budget_status.prefer_skip_llm and ec not in {
            ExecutionClass.PLANNING,
            ExecutionClass.LONG_RUNNING_GOAL,
            ExecutionClass.ANSWER,
            ExecutionClass.REASONING,
        }:
            skip = True
        if ec in {ExecutionClass.NO_AI}:
            skip = True
        # Pure tool paths only skip when explicitly requested
        if ec == ExecutionClass.DETERMINISTIC_TOOL and request.metadata.get("force_deterministic"):
            skip = True

        opts: list[str] = []
        if prefer_cheap:
            opts.append("budget_prefer_cheap")
        if budget_status.soft_warning:
            opts.append("budget_soft_warning")

        decision = GatewayDecision(
            execution_class=ec,
            selected_model=model,
            provider=provider,
            reason=f"{reason};{route_reason}",
            skip_llm=skip,
            prefer_cache=True,
            prefer_deterministic=ec in {ExecutionClass.DETERMINISTIC_TOOL, ExecutionClass.NO_AI},
            context_budget_tokens=ctx_budget,
            estimated_cost_usd=est_cost,
            estimated_input_tokens=est_in,
            estimated_output_tokens=est_out,
            optimizations=opts,
            fallback_models=fallbacks,
        )
        if not budget_status.allowed:
            decision.skip_llm = True
            decision.optimizations.append(f"blocked:{budget_status.reason}")
        return decision

    def complete(
        self,
        request: GatewayRequest,
        *,
        invoke: Callable[[str, list[dict], float, int | None], Any] | None = None,
    ) -> GatewayResult:
        """
        invoke(model, messages, temperature, max_tokens) -> object with .choices and .usage
        When invoke is None, raises — LlmProvider supplies invoke.
        """
        if not getattr(settings, "ai_gateway_enabled", True):
            # Legacy pass-through decision still built
            decision = self.plan(request)
        else:
            decision = self.plan(request)

        if decision.prefer_deterministic and decision.skip_llm:
            ai_governance.record(
                request.org_id, decision=decision, user_id=request.user_id, goal_id=request.goal_id, blocked=False
            )
            raise AIBudgetExceededError("no_ai_required")

        # Budget hard block
        if any(o.startswith("blocked:") for o in decision.optimizations):
            reason = next(o for o in decision.optimizations if o.startswith("blocked:")).split(":", 1)[1]
            ai_governance.record(
                request.org_id,
                decision=decision,
                user_id=request.user_id,
                goal_id=request.goal_id,
                blocked=True,
                block_reason=reason,
            )
            raise AIBudgetExceededError(reason)

        system = request.system_prompt or ""
        user = sanitize_user_prompt(request.user_prompt or "")
        system, user, opt_notes, est_tokens = prompt_optimizer.optimize(
            system, user, budget_tokens=decision.context_budget_tokens
        )
        decision.optimizations.extend(opt_notes)
        decision.estimated_input_tokens = est_tokens

        fp = prompt_optimizer.fingerprint(system, user)
        cache_hit = False
        if decision.prefer_cache and request.require_json is False or True:
            cached = gateway_cache.get_prompt_response(
                request.org_id,
                fingerprint=fp,
                model=decision.selected_model,
                execution_class=decision.execution_class.value,
            )
            if cached and cached.get("text"):
                cache_hit = True
                latency = 0.0
                text = str(cached["text"])
                pt = int(cached.get("prompt_tokens") or est_tokens)
                ct = int(cached.get("completion_tokens") or prompt_optimizer.estimate_tokens(text))
                cost = model_router.estimate_cost_usd(decision.selected_model, input_tokens=pt, output_tokens=ct)
                # Cached calls counted as savings
                result = GatewayResult(
                    text=text,
                    decision=decision,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=pt + ct,
                    cost_usd=0.0,
                    latency_ms=latency,
                    cache_hit=True,
                    model=decision.selected_model,
                    provider=decision.provider,
                    from_cache=True,
                )
                result.governance = ai_governance.record(
                    request.org_id, decision=decision, result=result, user_id=request.user_id, goal_id=request.goal_id
                )
                ai_usage_analytics.record(
                    request.org_id,
                    model=decision.selected_model,
                    execution_class=decision.execution_class.value,
                    tokens=pt + ct,
                    cost_usd=0.0,
                    latency_ms=0.0,
                    cache_hit=True,
                    saved_cost_usd=cost,
                )
                return result

        if invoke is None:
            raise RuntimeError("AI Gateway invoke callback required")

        llm_runtime_guard.check_circuit(request.org_id)
        llm_runtime_guard.reserve_tokens(request.org_id, estimated_tokens=max(est_tokens, request.estimated_tokens))

        # Credits reserve if charging
        op = request.operation_code
        if op:
            try:
                from app.modules.platform.billing.services.credit_service import credit_service

                credit_service.reserve_credits(request.org_id, op)
            except Exception:
                pass

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        started = time.perf_counter()
        last_error: Exception | None = None
        models_try = [decision.selected_model] + [m for m in decision.fallback_models if m != decision.selected_model]
        response = None
        used_model = decision.selected_model

        for mid in models_try:
            for delay in [0.0] + llm_runtime_guard.retry_delays():
                if delay > 0:
                    llm_runtime_guard.backoff(delay)
                try:
                    response = invoke(
                        mid,
                        messages,
                        request.temperature,
                        request.max_output_tokens,
                    )
                    used_model = mid
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    metrics_store.incr_llm_failure()
                    llm_runtime_guard.record_failure(request.org_id)
            if response is not None:
                break

        if response is None:
            ai_usage_analytics.record(
                request.org_id,
                model=used_model,
                execution_class=decision.execution_class.value,
                tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
                cache_hit=False,
                failed=True,
            )
            raise RuntimeError(f"LLM request failed after retries: {last_error}")

        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        llm_runtime_guard.record_success(request.org_id)
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else est_tokens
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        text = ""
        try:
            text = response.choices[0].message.content or ""
        except Exception:
            text = str(getattr(response, "text", "") or "")

        cost = model_router.estimate_cost_usd(
            used_model, input_tokens=prompt_tokens, output_tokens=completion_tokens
        )
        decision.selected_model = used_model

        credits_charged = 0.0
        if op:
            try:
                from app.modules.platform.billing.services.credit_service import credit_service

                credit_service.commit_deduction(request.org_id, op)
                credits_charged = float(credit_service.operation_cost(op))
            except Exception:
                pass

        tel = token_intelligence.build(
            org_id=request.org_id,
            provider=decision.provider,
            model=used_model,
            operation_code=op or request.usage_operation_code,
            execution_class=decision.execution_class.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_tokens=request.estimated_tokens,
            latency_ms=latency_ms,
            cache_hit=False,
            user_id=request.user_id,
            goal_id=request.goal_id,
            workflow_id=request.workflow_id,
            routing_reason=decision.reason,
            optimizations=decision.optimizations,
            estimated_cost_usd=decision.estimated_cost_usd,
        )
        # Fix cost on telemetry from actual
        tel.cost_usd = cost
        token_intelligence.persist_usage(tel, credits_charged=credits_charged)

        ai_budget_manager.commit(
            request.org_id, cost, user_id=request.user_id, goal_id=request.goal_id
        )
        ai_usage_analytics.record(
            request.org_id,
            model=used_model,
            execution_class=decision.execution_class.value,
            tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            cache_hit=False,
        )
        gateway_cache.set_prompt_response(
            request.org_id,
            fingerprint=fp,
            model=used_model,
            execution_class=decision.execution_class.value,
            payload={"text": text, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        )

        result = GatewayResult(
            text=text,
            decision=decision,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            cache_hit=False,
            model=used_model,
            provider=decision.provider,
        )
        result.governance = ai_governance.record(
            request.org_id, decision=decision, result=result, user_id=request.user_id, goal_id=request.goal_id
        )
        log_event(
            "ai.gateway.complete",
            org_id=request.org_id,
            model=used_model,
            latency_ms=latency_ms,
            cost_usd=cost,
            execution_class=decision.execution_class.value,
        )
        return result

    def should_use_llm_for_intent(self, heuristic_confidence: float) -> bool:
        return heuristic_confidence < 0.75 and getattr(settings, "ai_gateway_enabled", True)


ai_gateway = AIGateway()
