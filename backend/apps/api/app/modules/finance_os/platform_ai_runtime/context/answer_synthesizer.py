from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import (
    extract_user_facts,
    looks_like_context_dump,
    prompt_assembler,
    _try_parse_jsonish,
)
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.platform.billing.billing_hooks import billing_ai_operation
from app.services.llm_provider import llm_provider
from app.services.logger import log_event


def _coerce_answer(raw: str | None, ctx: PlatformContext, question: str) -> str:
    text = (raw or "").strip()
    if not text or looks_like_context_dump(text):
        return prompt_assembler.fallback_text(ctx, question)
    return text


class AnswerSynthesizer:
    def synthesize(self, org_id: str, ctx: PlatformContext, question: str) -> dict:
        with billing_ai_operation(org_id, feature="agents", operation_code="m38_answer", skip_credits=True):
            system, user_prompt = prompt_assembler.build_answer_prompt(ctx, question)
            pre_facts = extract_user_facts(ctx)
            sources = {
                "retrieval_trace": ctx.retrieval_trace,
                "entities": [e.model_dump() for e in ctx.entities],
                "summaries": list(ctx.summaries.keys()),
                "facts": pre_facts,
            }
            fallback = prompt_assembler.fallback_text(ctx, question)

            if not llm_provider.is_ready():
                return {
                    "answer": fallback,
                    "sources": sources,
                    "confidence_band": "manual",
                    "facts": pre_facts,
                    "data_gaps": [],
                }
            try:
                raw = llm_provider.generate_text(
                    org_id=org_id,
                    system_prompt=system
                    + "\nReturn ONLY compact JSON. No prose outside JSON. No markdown fences.",
                    user_prompt=user_prompt,
                    estimated_tokens=min(2000, max(800, ctx.token_estimate + 400)),
                    usage_operation_code="m38_answer",
                    execution_class="answer",
                    intent=ctx.intent.intent if ctx.intent else "read",
                    max_output_tokens=1200,
                    temperature=0.1,
                )
                out = _try_parse_jsonish(raw) if isinstance(raw, str) else {}
                if not isinstance(out, dict):
                    out = {}
                if out.get("answer"):
                    answer = _coerce_answer(str(out.get("answer")), ctx, question)
                    facts = out.get("facts") if isinstance(out.get("facts"), list) else pre_facts
                    gaps = out.get("data_gaps") if isinstance(out.get("data_gaps"), list) else []
                    return {
                        "answer": answer,
                        "sources": sources,
                        "confidence_band": str(out.get("confidence_band") or "review"),
                        "facts": facts or pre_facts,
                        "data_gaps": [str(g) for g in gaps][:8],
                    }
                # Model returned plain prose
                plain = _coerce_answer(raw, ctx, question)
                return {
                    "answer": plain,
                    "sources": sources,
                    "confidence_band": "review",
                    "facts": pre_facts,
                    "data_gaps": [],
                }
            except Exception as exc:
                log_event(
                    "m38.answer_synthesizer.failed",
                    org_id=org_id,
                    detail=str(exc)[:300],
                )
                return {
                    "answer": fallback,
                    "sources": sources,
                    "confidence_band": "manual",
                    "facts": pre_facts,
                    "data_gaps": [],
                }


answer_synthesizer = AnswerSynthesizer()
