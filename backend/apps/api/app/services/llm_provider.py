import json
import os
from typing import Any

from openai import OpenAI

from app.core.config import settings
from app.services.ai_gateway.gateway import AIBudgetExceededError, ai_gateway
from app.services.ai_gateway.types import ExecutionClass, GatewayRequest
from app.services.llm_runtime import llm_runtime_guard
from app.services.metrics import metrics_store
from app.services.logger import log_event


class LlmProvider:
    """OpenAI client facade — every chat/JSON call routes through AI Gateway (Wave 6)."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            self.client = None
            return
        kwargs: dict = {"api_key": settings.openai_api_key}
        base_url = (settings.openai_base_url or "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
        self.client = OpenAI(**kwargs)

    def is_ready(self) -> bool:
        return self.client is not None and settings.llm_provider == "openai"

    def _invoke_chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None,
    ) -> Any:
        if not self.client:
            raise RuntimeError("LLM provider is not configured. Set OPENAI_API_KEY.")
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": settings.llm_timeout_seconds,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return self.client.chat.completions.create(**kwargs)

    def generate_text(
        self,
        org_id: str,
        system_prompt: str,
        user_prompt: str,
        estimated_tokens: int = 1500,
        *,
        operation_code: str | None = None,
        usage_operation_code: str | None = None,
        execution_class: str | ExecutionClass | None = None,
        intent: str | None = None,
        user_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        model_override: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        if not self.is_ready():
            raise RuntimeError("LLM provider is not configured. Set OPENAI_API_KEY.")

        if not getattr(settings, "ai_gateway_enabled", True):
            return self._legacy_generate_text(
                org_id,
                system_prompt,
                user_prompt,
                estimated_tokens,
                operation_code=operation_code,
                usage_operation_code=usage_operation_code,
            )

        req = GatewayRequest(
            org_id=org_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            estimated_tokens=estimated_tokens,
            operation_code=operation_code,
            usage_operation_code=usage_operation_code,
            execution_class=execution_class,
            intent=intent,
            user_id=user_id,
            goal_id=goal_id,
            workflow_id=workflow_id,
            model_override=model_override,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata or {},
        )
        try:
            result = ai_gateway.complete(req, invoke=self._invoke_chat)
            return result.text
        except AIBudgetExceededError:
            log_event("ai.gateway.budget_blocked", org_id=org_id, operation=operation_code or usage_operation_code or "")
            raise
        except RuntimeError as exc:
            if "deterministic_path_no_llm" in str(exc):
                # Caller should not reach LLM for pure tool paths; re-raise clearly
                raise
            raise

    def generate_json(
        self,
        org_id: str,
        system_prompt: str,
        user_prompt: str,
        estimated_tokens: int = 1500,
        *,
        operation_code: str | None = None,
        usage_operation_code: str | None = None,
        execution_class: str | ExecutionClass | None = None,
        intent: str | None = None,
        user_id: str | None = None,
        goal_id: str | None = None,
        **kwargs,
    ) -> dict:
        raw = self.generate_text(
            org_id=org_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            estimated_tokens=estimated_tokens,
            operation_code=operation_code,
            usage_operation_code=usage_operation_code,
            execution_class=execution_class or ExecutionClass.ANSWER,
            intent=intent,
            user_id=user_id,
            goal_id=goal_id,
            **{k: v for k, v in kwargs.items() if k in {"model_override", "temperature", "max_output_tokens", "metadata", "workflow_id"}},
        )
        raw = (raw or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        return json.loads(raw)

    def generate_embedding(self, org_id: str, text: str) -> list[float]:
        if not self.is_ready():
            raise RuntimeError("LLM provider is not configured. Set OPENAI_API_KEY.")
        # Gateway decision for cost telemetry; embeddings still need direct embeddings API
        from app.services.ai_gateway.model_router import model_router
        from app.services.ai_gateway.budget_manager import ai_budget_manager
        from app.services.ai_gateway.token_intel import token_intelligence
        from app.services.ai_gateway.analytics import ai_usage_analytics

        model = settings.retrieval_embedding_model
        est_tokens = max(50, len(text) // 4)
        est_cost = model_router.estimate_cost_usd(model, input_tokens=est_tokens, output_tokens=0)
        status = ai_budget_manager.check(org_id, estimated_cost_usd=est_cost)
        if not status.allowed:
            raise AIBudgetExceededError(status.reason)

        llm_runtime_guard.check_circuit(org_id)
        llm_runtime_guard.reserve_tokens(org_id, estimated_tokens=min(800, est_tokens + 100))
        last_error: Exception | None = None
        started = __import__("time").perf_counter()
        for delay in [0.0] + llm_runtime_guard.retry_delays():
            if delay > 0:
                llm_runtime_guard.backoff(delay)
            try:
                response = self.client.embeddings.create(
                    model=model,
                    input=text,
                    timeout=settings.llm_timeout_seconds,
                )
                if not response.data:
                    raise RuntimeError("Embedding response returned no data")
                llm_runtime_guard.record_success(org_id)
                usage = getattr(response, "usage", None)
                pt = int(getattr(usage, "total_tokens", 0) or getattr(usage, "prompt_tokens", 0) or est_tokens) if usage else est_tokens
                latency = round((__import__("time").perf_counter() - started) * 1000.0, 2)
                cost = model_router.estimate_cost_usd(model, input_tokens=pt, output_tokens=0)
                tel = token_intelligence.build(
                    org_id=org_id,
                    provider=settings.llm_provider,
                    model=model,
                    operation_code="embedding",
                    execution_class=ExecutionClass.EMBEDDING.value,
                    prompt_tokens=pt,
                    completion_tokens=0,
                    estimated_tokens=est_tokens,
                    latency_ms=latency,
                )
                tel.cost_usd = cost
                token_intelligence.persist_usage(tel, credits_charged=0.0)
                ai_budget_manager.commit(org_id, cost)
                ai_usage_analytics.record(
                    org_id,
                    model=model,
                    execution_class=ExecutionClass.EMBEDDING.value,
                    tokens=pt,
                    cost_usd=cost,
                    latency_ms=latency,
                    cache_hit=False,
                )
                return [float(x) for x in response.data[0].embedding]
            except Exception as exc:
                last_error = exc
                metrics_store.incr_llm_failure()
                llm_runtime_guard.record_failure(org_id)
        raise RuntimeError(f"Embedding request failed after retries: {last_error}")

    def _legacy_generate_text(
        self,
        org_id: str,
        system_prompt: str,
        user_prompt: str,
        estimated_tokens: int,
        *,
        operation_code: str | None,
        usage_operation_code: str | None,
    ) -> str:
        """Pre-Wave-6 path kept for kill-switch compatibility."""
        from app.core.prompt_sanitizer import sanitize_user_prompt

        user_prompt = sanitize_user_prompt(user_prompt)
        llm_runtime_guard.check_circuit(org_id)
        if operation_code:
            try:
                from app.modules.platform.billing.services.credit_service import credit_service

                credit_service.reserve_credits(org_id, operation_code)
            except Exception:
                pass
        llm_runtime_guard.reserve_tokens(org_id, estimated_tokens=estimated_tokens)
        last_error: Exception | None = None
        for delay in [0.0] + llm_runtime_guard.retry_delays():
            if delay > 0:
                llm_runtime_guard.backoff(delay)
            try:
                response = self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    timeout=settings.llm_timeout_seconds,
                )
                llm_runtime_guard.record_success(org_id)
                usage = getattr(response, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
                if operation_code:
                    try:
                        from app.modules.platform.billing.services.credit_service import credit_service

                        credit_service.commit_deduction(org_id, operation_code)
                        credit_service.log_ai_usage(
                            org_id,
                            provider="openai",
                            model=settings.openai_model,
                            operation_code=operation_code,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            credits_charged=credit_service.operation_cost(operation_code),
                        )
                    except Exception:
                        pass
                elif usage_operation_code:
                    try:
                        from app.modules.platform.billing.services.credit_service import credit_service

                        credit_service.log_ai_usage(
                            org_id,
                            provider="openai",
                            model=settings.openai_model,
                            operation_code=usage_operation_code,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            credits_charged=0.0,
                        )
                    except Exception:
                        pass
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_error = exc
                metrics_store.incr_llm_failure()
                llm_runtime_guard.record_failure(org_id)
        raise RuntimeError(f"LLM request failed after retries: {last_error}")


llm_provider = LlmProvider()
