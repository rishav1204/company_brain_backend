from __future__ import annotations

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.context.answer_synthesizer import answer_synthesizer
from app.modules.finance_os.platform_ai_runtime.context.context_compressor import context_compressor
from app.modules.finance_os.platform_ai_runtime.context.context_planner import context_planner
from app.modules.finance_os.platform_ai_runtime.context.context_ranker import context_ranker
from app.modules.finance_os.platform_ai_runtime.context.entity_resolver import entity_resolver
from app.modules.finance_os.platform_ai_runtime.context.intent_engine import intent_engine
from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler
from app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator import retrieval_orchestrator
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import ConversationState, PlatformContext
from app.modules.finance_os.platform_ai_runtime.context.working_memory import working_memory
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState
from app.modules.platform.billing.billing_hooks import billing_ai_operation
from app.services.logger import log_event
from app.services.repositories import audit_repo


class PlatformContextEngine:
    def build(
        self,
        org_id: str,
        *,
        message: str,
        world_state: WorldState,
        goal_id: str | None = None,
        user_id: str = "platform_context",
        roles: list[str] | None = None,
    ) -> PlatformContext:
        if not settings.m38_context_engine_enabled:
            intent = intent_engine.classify(message, use_llm=False)
            return PlatformContext(intent=intent, world_state=world_state, question=message)

        wm = working_memory.load(org_id, goal_id) if settings.m38_working_memory else ConversationState()
        conv = wm

        intent = intent_engine.classify(message)
        entities = entity_resolver.resolve(message, world_state=world_state, working_memory=conv)
        plan = context_planner.plan(intent=intent, entities=entities, world_state=world_state, message=message)

        with billing_ai_operation(org_id, feature="agents", operation_code="m38_context_build"):
            raw = retrieval_orchestrator.fetch(
                org_id,
                plan=plan,
                world_state=world_state,
                entities=entities,
                user_id=user_id,
                roles=roles,
            )

        memory = context_ranker.rank_memory(raw.get("memory") or [], query=message, world_state=world_state, entities=entities)
        graph = context_ranker.rank_graph(raw.get("graph") or [])
        documents = context_ranker.rank_documents(raw.get("documents") or [])

        ctx = PlatformContext(
            intent=intent,
            entities=entities,
            world_state=world_state,
            memory=memory,
            graph=graph,
            erp_facts=raw.get("erp_facts") or {},
            documents=documents,
            policies=raw.get("policies") or [],
            working_memory=conv,
            retrieval_trace=raw.get("retrieval_trace") or [],
            question=message,
        )
        ctx = context_compressor.compress(ctx)

        self._audit_context(org_id, ctx, user_id=user_id)
        log_event(
            "m38.context.built",
            intent=intent.intent,
            entities=len(entities),
            token_estimate=ctx.token_estimate,
            sources=len(ctx.retrieval_trace),
        )
        return ctx

    def persist_turn(
        self,
        org_id: str,
        goal_id: str,
        ctx: PlatformContext,
    ) -> None:
        if not settings.m38_working_memory:
            return
        working_memory.save(
            org_id,
            goal_id,
            state=ctx.working_memory,
            entities=ctx.entities,
            intent=ctx.intent.intent,
        )

    def planner_context_text(self, ctx: PlatformContext) -> str:
        return prompt_assembler.build_planner_context_block(ctx)

    def _audit_context(self, org_id: str, ctx: PlatformContext, *, user_id: str) -> None:
        try:
            audit_repo.create_log(
                org_id=org_id,
                actor_type="agent",
                actor_id="platform_context_engine",
                event_type="m38.context.retrieved",
                object_ref=f"context:{ctx.intent.intent}",
                payload_jsonb={
                    "intent": ctx.intent.intent,
                    "entities": len(ctx.entities),
                    "token_estimate": ctx.token_estimate,
                    "sources": [t.get("source") for t in ctx.retrieval_trace],
                    "user_id": user_id,
                },
            )
        except Exception:
            pass


platform_context_engine = PlatformContextEngine()
