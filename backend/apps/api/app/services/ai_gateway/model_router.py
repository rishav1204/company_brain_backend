"""Model router — provider-agnostic, config-driven (Wave 6)."""

from __future__ import annotations

import json

from app.core.config import settings
from app.services.ai_gateway.types import ExecutionClass


# Default alias → model id when LLM_PROVIDER=openai
_DEFAULT_ALIASES_OPENAI: dict[str, str] = {
    "cheap": "gpt-4.1-mini",
    "standard": "gpt-4.1",
    "strong": "gpt-4.1",
    "embedding": "text-embedding-3-small",
    "vision": "gpt-4.1",
}

# Default alias → model id when LLM_PROVIDER=anthropic (Haiku for responses by default)
_DEFAULT_ALIASES_ANTHROPIC: dict[str, str] = {
    "cheap": "claude-3-5-haiku-latest",
    "standard": "claude-3-5-haiku-latest",
    "strong": "claude-3-5-haiku-latest",
    "embedding": "text-embedding-3-small",  # embeddings still via OpenAI when configured
    "vision": "claude-3-5-haiku-latest",
}

_DEFAULT_CLASS_TO_ALIAS: dict[str, str] = {
    ExecutionClass.NO_AI.value: "cheap",
    ExecutionClass.DETERMINISTIC_TOOL.value: "cheap",
    ExecutionClass.RETRIEVAL.value: "cheap",
    ExecutionClass.INTENT_CLASSIFY.value: "cheap",
    ExecutionClass.ANSWER.value: "standard",
    ExecutionClass.REASONING.value: "standard",
    ExecutionClass.PLANNING.value: "strong",
    ExecutionClass.AGENTIC_WORKFLOW.value: "strong",
    ExecutionClass.LONG_RUNNING_GOAL.value: "strong",
    ExecutionClass.EMBEDDING.value: "embedding",
    ExecutionClass.OCR_VISION.value: "vision",
}

# Approx USD per 1M tokens if caller needs estimate (overridable)
_DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-4.1-mini": {"input": 0.4, "output": 1.6},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "claude-3-5-haiku-latest": {"input": 0.8, "output": 4.0},
    "claude-3-5-haiku-20241022": {"input": 0.8, "output": 4.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-0": {"input": 3.0, "output": 15.0},
    "default": {"input": 2.0, "output": 8.0},
}


class ModelRouter:
    def provider(self) -> str:
        return (getattr(settings, "llm_provider", "openai") or "openai").strip().lower()

    def aliases(self) -> dict[str, str]:
        provider = self.provider()
        if provider == "anthropic":
            aliases = dict(_DEFAULT_ALIASES_ANTHROPIC)
            haiku = (
                (getattr(settings, "ai_chat_model", None) or "").strip()
                or (getattr(settings, "anthropic_model", None) or "").strip()
                or aliases["standard"]
            )
            aliases["standard"] = haiku
            cheap = (
                (getattr(settings, "anthropic_model_cheap", None) or "").strip()
                or (getattr(settings, "ai_model_cheap", None) or "").strip()
            )
            # Ignore OpenAI-named cheap models when chat provider is Anthropic
            if cheap and not cheap.lower().startswith("claude"):
                cheap = ""
            aliases["cheap"] = cheap or haiku
            strong = (
                (getattr(settings, "anthropic_model_strong", None) or "").strip()
                or (getattr(settings, "ai_model_strong", None) or "").strip()
            )
            if strong and not strong.lower().startswith("claude"):
                strong = ""
            aliases["strong"] = strong or haiku
            vis = (getattr(settings, "ai_model_vision", None) or "").strip()
            if vis and not vis.lower().startswith("claude"):
                vis = ""
            aliases["vision"] = vis or haiku
        else:
            aliases = dict(_DEFAULT_ALIASES_OPENAI)
            aliases["standard"] = (
                (getattr(settings, "ai_chat_model", None) or "").strip()
                or (getattr(settings, "openai_model", None) or "").strip()
                or aliases["standard"]
            )
            aliases["strong"] = (
                (getattr(settings, "ai_model_strong", None) or "").strip() or aliases["standard"]
            )
            aliases["cheap"] = (getattr(settings, "ai_model_cheap", None) or "").strip() or "gpt-4.1-mini"
            aliases["vision"] = (
                (getattr(settings, "ai_model_vision", None) or "").strip() or aliases["standard"]
            )

        aliases["embedding"] = (
            getattr(settings, "retrieval_embedding_model", None) or aliases.get("embedding") or "text-embedding-3-small"
        )
        # JSON override: {"cheap":"...", "standard":"..."}
        raw = (getattr(settings, "ai_model_routes_json", "") or "").strip()
        if raw:
            try:
                extra = json.loads(raw)
                if isinstance(extra, dict):
                    aliases.update({str(k): str(v) for k, v in extra.items()})
            except Exception:
                pass
        return aliases

    def class_map(self) -> dict[str, str]:
        m = dict(_DEFAULT_CLASS_TO_ALIAS)
        raw = (getattr(settings, "ai_class_routes_json", "") or "").strip()
        if raw:
            try:
                extra = json.loads(raw)
                if isinstance(extra, dict):
                    m.update({str(k): str(v) for k, v in extra.items()})
            except Exception:
                pass
        return m

    def resolve(
        self,
        execution_class: ExecutionClass,
        *,
        complexity: float = 0.5,
        model_override: str | None = None,
        prefer_cheap: bool = False,
        provider_health_ok: bool = True,
    ) -> tuple[str, str, list[str], str]:
        """Return (model_id, provider, fallbacks, reason)."""
        aliases = self.aliases()
        provider = self.provider()
        if provider in {"none", "off", "disabled"}:
            provider = "none"

        if model_override:
            return model_override, provider, [aliases.get("cheap") or aliases.get("standard", "")], "override"

        alias = self.class_map().get(execution_class.value, "standard")
        if prefer_cheap or complexity < 0.4:
            if execution_class not in {
                ExecutionClass.PLANNING,
                ExecutionClass.LONG_RUNNING_GOAL,
                ExecutionClass.EMBEDDING,
            }:
                alias = "cheap"
                reason = f"class={execution_class.value}+prefer_cheap"
            else:
                reason = f"class={execution_class.value}+alias={alias}"
        elif complexity >= 0.75 and execution_class in {
            ExecutionClass.REASONING,
            ExecutionClass.ANSWER,
        }:
            alias = "strong"
            reason = f"class={execution_class.value}+high_complexity"
        else:
            reason = f"class={execution_class.value}+alias={alias}"

        model = aliases.get(alias) or aliases.get("standard") or ""
        fallbacks: list[str] = []
        for a in ("standard", "cheap", "strong"):
            mid = aliases.get(a)
            if mid and mid != model and mid not in fallbacks:
                fallbacks.append(mid)

        if not provider_health_ok and fallbacks:
            model = fallbacks[0]
            reason += "+health_fallback"

        return model, provider, fallbacks, reason

    def unit_prices(self, model: str) -> dict[str, float]:
        prices = dict(_DEFAULT_PRICES)
        raw = (getattr(settings, "ai_model_prices_json", "") or "").strip()
        if raw:
            try:
                extra = json.loads(raw)
                if isinstance(extra, dict):
                    for k, v in extra.items():
                        if isinstance(v, dict):
                            prices[str(k)] = {
                                "input": float(v.get("input", 2.0)),
                                "output": float(v.get("output", 8.0)),
                            }
            except Exception:
                pass
        if model in prices:
            return prices[model]
        # prefix match for dated anthropic ids
        for key, val in prices.items():
            if key != "default" and model.startswith(key):
                return val
        return prices.get("default") or {"input": 2.0, "output": 8.0}

    def estimate_cost_usd(self, model: str, *, input_tokens: int, output_tokens: int) -> float:
        p = self.unit_prices(model)
        # prices are USD per 1M tokens
        return round((input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000.0, 8)


model_router = ModelRouter()
