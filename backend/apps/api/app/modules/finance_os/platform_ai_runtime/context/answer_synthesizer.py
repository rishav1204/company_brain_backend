from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.platform.billing.billing_hooks import billing_ai_operation
from app.services.llm_provider import llm_provider


class AnswerSynthesizer:
    def synthesize(self, org_id: str, ctx: PlatformContext, question: str) -> dict:
        with billing_ai_operation(org_id, feature="agents", operation_code="m38_answer"):
            system, user_prompt = prompt_assembler.build_answer_prompt(ctx, question)
            sources = {
                "retrieval_trace": ctx.retrieval_trace,
                "entities": [e.model_dump() for e in ctx.entities],
                "summaries": list(ctx.summaries.keys()),
            }
            if not llm_provider.is_ready():
                return {
                    "answer": prompt_assembler.fallback_text(ctx),
                    "sources": sources,
                    "confidence_band": "manual",
                }
            try:
                out = llm_provider.generate_json(
                    org_id=org_id,
                    system_prompt=system,
                    user_prompt=user_prompt + '\n\nReturn JSON: {"answer": str, "confidence_band": str}',
                    estimated_tokens=min(2000, max(800, ctx.token_estimate + 400)),
                )
                return {
                    "answer": str(out.get("answer") or prompt_assembler.fallback_text(ctx)),
                    "sources": sources,
                    "confidence_band": str(out.get("confidence_band") or "review"),
                }
            except Exception:
                return {
                    "answer": prompt_assembler.fallback_text(ctx),
                    "sources": sources,
                    "confidence_band": "manual",
                }


answer_synthesizer = AnswerSynthesizer()
