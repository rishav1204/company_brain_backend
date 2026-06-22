import json
import os

from openai import OpenAI

from app.core.config import settings
from app.services.llm_runtime import llm_runtime_guard
from app.services.metrics import metrics_store


class LlmProvider:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            self.client = None
            return
        kwargs: dict = {"api_key": settings.openai_api_key}
        base_url = (settings.openai_base_url or "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        else:
            # Empty OPENAI_BASE_URL in .env breaks httpx ("missing protocol").
            os.environ.pop("OPENAI_BASE_URL", None)
        self.client = OpenAI(**kwargs)
    def is_ready(self) -> bool:
        return self.client is not None and settings.llm_provider == "openai"

    def generate_text(
        self,
        org_id: str,
        system_prompt: str,
        user_prompt: str,
        estimated_tokens: int = 1500,
        *,
        operation_code: str | None = None,
    ) -> str:
        if not self.is_ready():
            raise RuntimeError("LLM provider is not configured. Set OPENAI_API_KEY.")
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
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_error = exc
                metrics_store.incr_llm_failure()
                llm_runtime_guard.record_failure(org_id)
        raise RuntimeError(f"LLM request failed after retries: {last_error}")

    def generate_json(
        self,
        org_id: str,
        system_prompt: str,
        user_prompt: str,
        estimated_tokens: int = 1500,
        *,
        operation_code: str | None = None,
    ) -> dict:
        raw = self.generate_text(
            org_id=org_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            estimated_tokens=estimated_tokens,
            operation_code=operation_code,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        return json.loads(raw)

    def generate_embedding(self, org_id: str, text: str) -> list[float]:
        if not self.is_ready():
            raise RuntimeError("LLM provider is not configured. Set OPENAI_API_KEY.")
        llm_runtime_guard.check_circuit(org_id)
        llm_runtime_guard.reserve_tokens(org_id, estimated_tokens=800)
        last_error: Exception | None = None
        for delay in [0.0] + llm_runtime_guard.retry_delays():
            if delay > 0:
                llm_runtime_guard.backoff(delay)
            try:
                response = self.client.embeddings.create(
                    model=settings.retrieval_embedding_model,
                    input=text,
                    timeout=settings.llm_timeout_seconds,
                )
                if not response.data:
                    raise RuntimeError("Embedding response returned no data")
                llm_runtime_guard.record_success(org_id)
                return [float(x) for x in response.data[0].embedding]
            except Exception as exc:
                last_error = exc
                metrics_store.incr_llm_failure()
                llm_runtime_guard.record_failure(org_id)
        raise RuntimeError(f"Embedding request failed after retries: {last_error}")

llm_provider = LlmProvider()
