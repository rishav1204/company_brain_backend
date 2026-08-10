from __future__ import annotations

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.context.answer_synthesizer import answer_synthesizer
from app.modules.finance_os.platform_ai_runtime.context.context_compressor import context_compressor
from app.modules.finance_os.platform_ai_runtime.context.context_planner import context_planner
from app.modules.finance_os.platform_ai_runtime.context.context_quality import context_quality_evaluator
from app.modules.finance_os.platform_ai_runtime.context.context_ranker import context_ranker
from app.modules.finance_os.platform_ai_runtime.context.entity_resolver import entity_resolver
from app.modules.finance_os.platform_ai_runtime.context.intent_engine import intent_engine
from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler
from app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator import retrieval_orchestrator
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ContextItemMeta,
    ConversationState,
    PlatformContext,
)
from app.modules.finance_os.platform_ai_runtime.context.working_memory import working_memory
from app.modules.finance_os.platform_ai_runtime.context.world_state_engine import world_state_engine
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState
from app.modules.finance_os.platform_ai_runtime.security.ai_firewall import ai_firewall
from app.modules.finance_os.platform_ai_runtime.security.context_boundary import session_scope
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
        attrs: dict | None = None,
    ) -> PlatformContext:
        safe_message = ai_firewall.enforce(
            message, org_id=org_id, user_id=user_id, stage="context_message", goal_id=goal_id
        )

        # Resolve session world state (UI publish + persisted goal)
        ws = world_state_engine.resolve(
            org_id, published=world_state, goal_id=goal_id, roles=roles
        )

        if not settings.m38_context_engine_enabled:
            intent = intent_engine.classify(safe_message, use_llm=False)
            return PlatformContext(intent=intent, world_state=ws, question=safe_message)

        wm = working_memory.load(org_id, goal_id) if settings.m38_working_memory else ConversationState()
        conv = wm

        intent = intent_engine.classify(safe_message)
        resolution = entity_resolver.resolve_v2(
            safe_message, world_state=ws, working_memory=conv, org_id=org_id
        )
        entities = resolution.entities
        plan = context_planner.plan(
            intent=intent, entities=entities, world_state=ws, message=safe_message
        )

        scope = session_scope(org_id, ws, attrs)
        with billing_ai_operation(org_id, feature="agents", operation_code="m38_context_build"):
            raw = retrieval_orchestrator.fetch(
                org_id,
                plan=plan,
                world_state=ws,
                entities=entities,
                user_id=user_id,
                roles=roles,
                goal_id=goal_id,
                attrs=attrs or scope,
            )

        memory = context_ranker.rank_memory(
            raw.get("memory") or [],
            query=safe_message,
            world_state=ws,
            entities=entities,
            intent=intent,
        )
        graph = context_ranker.rank_graph(
            raw.get("graph") or [],
            query=safe_message,
            world_state=ws,
            entities=entities,
            intent=intent,
        )
        documents = context_ranker.rank_documents(
            raw.get("documents") or [],
            query=safe_message,
            world_state=ws,
            entities=entities,
            intent=intent,
        )
        approvals = context_ranker.rank_approvals(raw.get("approval_queue") or [], world_state=ws)
        workflows = list(raw.get("workflow_state") or [])
        recent_events = list(raw.get("recent_events") or [])

        safe_docs: list[dict] = []
        for doc in documents:
            if isinstance(doc, dict):
                content = str(doc.get("content") or "")
                scrubbed = ai_firewall.inspect_document_as_data(
                    content, org_id=org_id, user_id=user_id
                )
                safe_docs.append({**doc, "content": scrubbed.sanitized_text})
            else:
                safe_docs.append(doc)

        item_meta = [
            ContextItemMeta(**m) if isinstance(m, dict) else m
            for m in (raw.get("item_meta") or [])
        ]

        ctx = PlatformContext(
            intent=intent,
            entities=entities,
            entity_resolution=resolution,
            world_state=ws,
            memory=memory,
            graph=graph,
            erp_facts=raw.get("erp_facts") or {},
            documents=safe_docs,
            policies=raw.get("policies") or [],
            workflow_state=workflows,
            approval_queue=approvals,
            recent_events=recent_events,
            working_memory=conv,
            retrieval_trace=raw.get("retrieval_trace") or [],
            retrieval_complete=bool(raw.get("retrieval_complete", True)),
            retrieval_failures=list(raw.get("retrieval_failures") or []),
            retrieval_plan=plan,
            item_meta=item_meta,
            question=safe_message,
            clarification_required=bool(resolution.needs_clarification),
            clarification_prompt=resolution.clarification_prompt,
            context_cache_hit=bool(raw.get("context_cache_hit")),
        )
        ctx = context_compressor.compress(ctx)

        quality = context_quality_evaluator.evaluate(ctx)
        ctx = ctx.model_copy(update={"quality": quality})

        # Expand retrieval once when quality insufficient (never guess)
        if quality.action == "expand_retrieval":
            expand = context_quality_evaluator.expansion_plan(ctx, quality)
            if expand:
                with billing_ai_operation(org_id, feature="agents", operation_code="m38_context_expand"):
                    extra = retrieval_orchestrator.fetch(
                        org_id,
                        plan=expand,
                        world_state=ws,
                        entities=entities,
                        user_id=user_id,
                        roles=roles,
                        goal_id=goal_id,
                        attrs=attrs or scope,
                        use_cache=False,
                    )
                mem2 = context_ranker.rank_memory(
                    list(ctx.memory) + list(extra.get("memory") or []),
                    query=safe_message,
                    world_state=ws,
                    entities=entities,
                    intent=intent,
                )
                graph2 = context_ranker.rank_graph(
                    list(ctx.graph) + list(extra.get("graph") or []),
                    query=safe_message,
                    world_state=ws,
                    entities=entities,
                    intent=intent,
                )
                erp2 = dict(ctx.erp_facts)
                erp2.update(extra.get("erp_facts") or {})
                failures = list(ctx.retrieval_failures) + list(extra.get("retrieval_failures") or [])
                trace = list(ctx.retrieval_trace) + list(extra.get("retrieval_trace") or [])
                ctx = ctx.model_copy(
                    update={
                        "memory": mem2,
                        "graph": graph2,
                        "erp_facts": erp2,
                        "retrieval_trace": trace,
                        "retrieval_failures": failures,
                        "retrieval_complete": bool(extra.get("retrieval_complete", True)) and not failures,
                    }
                )
                ctx = context_compressor.compress(ctx)
                quality = context_quality_evaluator.evaluate(ctx)
                ctx = ctx.model_copy(update={"quality": quality})

        # Persist merged world state on goal when present
        if goal_id:
            try:
                world_state_engine.publish(org_id, ws, goal_id=goal_id, user_id=user_id)
            except Exception as exc:
                log_event("m38.world_state.persist_failed", org_id=org_id, goal_id=goal_id, detail=str(exc))

        self._audit_context(org_id, ctx, user_id=user_id, scope=scope)
        log_event(
            "m38.context.built",
            intent=intent.intent,
            entities=len(entities),
            token_estimate=ctx.token_estimate,
            sources=len(ctx.retrieval_trace),
            clarification_required=ctx.clarification_required,
            retrieval_complete=ctx.retrieval_complete,
            quality_sufficient=bool(ctx.quality and ctx.quality.sufficient),
            cache_hit=ctx.context_cache_hit,
        )
        return ctx

    def persist_turn(
        self,
        org_id: str,
        goal_id: str,
        ctx: PlatformContext,
        *,
        user_message: str | None = None,
        assistant_summary: str | None = None,
    ) -> None:
        if not settings.m38_working_memory:
            return
        working_memory.save(
            org_id,
            goal_id,
            state=ctx.working_memory,
            entities=ctx.entities,
            intent=ctx.intent.intent,
            user_message=user_message or ctx.question,
            assistant_summary=assistant_summary,
            task=ctx.working_memory.current_task,
            reasoning_step=f"intent={ctx.intent.intent}; entities={len(ctx.entities)}",
        )
        try:
            world_state_engine.publish(org_id, ctx.world_state, goal_id=goal_id)
        except Exception as exc:
            log_event("m38.world_state.persist_failed", org_id=org_id, goal_id=goal_id, detail=str(exc))

    def planner_context_text(self, ctx: PlatformContext) -> str:
        return prompt_assembler.build_planner_context_block(ctx)

    def _audit_context(
        self, org_id: str, ctx: PlatformContext, *, user_id: str, scope: dict | None = None
    ) -> None:
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
                    "quality": ctx.quality.model_dump() if ctx.quality else None,
                    "scope": {
                        "company_id": (scope or {}).get("company_id"),
                        "branch_id": (scope or {}).get("branch_id"),
                    },
                },
            )
        except Exception as exc:
            log_event("m38.context.audit_failed", org_id=org_id, detail=str(exc))


platform_context_engine = PlatformContextEngine()
