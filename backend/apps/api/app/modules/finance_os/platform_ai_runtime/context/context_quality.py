"""Context quality evaluation — expand retrieval when insufficient (Wave 4)."""

from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ContextQuality,
    PlatformContext,
    RetrievalPlan,
    RetrievalSource,
)


class ContextQualityEvaluator:
    def evaluate(self, ctx: PlatformContext) -> ContextQuality:
        missing: list[str] = []
        has_entity = any(e.entity_id for e in ctx.entities)
        has_screen = bool(ctx.world_state and ctx.world_state.screen and ctx.world_state.screen.entity_id)
        has_erp = bool(ctx.erp_facts)
        has_mem = bool(ctx.memory)
        has_graph = bool(ctx.graph)
        has_docs = bool(ctx.documents)
        has_failures = bool(ctx.retrieval_failures)

        # Completeness: did we get something useful for the question?
        parts = [has_erp or has_mem or has_graph or has_docs, has_entity or has_screen or not self._needs_entity(ctx)]
        completeness = sum(1 for p in parts if p) / max(len(parts), 1)

        sources_ok = len(ctx.retrieval_trace or [])
        sources_failed = len(ctx.retrieval_failures or [])
        coverage = sources_ok / max(sources_ok + sources_failed, 1) if (sources_ok or sources_failed) else (1.0 if has_erp else 0.3)

        confidences = [e.confidence for e in ctx.entities if e.entity_id] or [0.5]
        confidence = sum(confidences) / len(confidences)

        fresh_vals = [m.freshness for m in (ctx.item_meta or [])] or [1.0]
        freshness = sum(fresh_vals) / len(fresh_vals)

        relevance = 0.5
        if has_screen and has_entity:
            relevance = 0.9
        elif has_screen or has_entity:
            relevance = 0.75
        if has_failures and not (has_erp or has_mem):
            relevance *= 0.6

        tokens = int(ctx.token_estimate or 0)

        if ctx.clarification_required:
            missing.append("entity_disambiguation")
        if self._needs_entity(ctx) and not has_entity and not has_screen:
            missing.append("current_entity")
        if not has_erp and not has_mem and "read" in (ctx.intent.intent or "read"):
            missing.append("business_data")
        if has_failures:
            missing.append("failed_sources")

        sufficient = (
            completeness >= 0.5
            and relevance >= 0.45
            and not ctx.clarification_required
            and ("business_data" not in missing or bool(ctx.summaries))
        )
        action = "ok"
        if ctx.clarification_required:
            action = "clarify"
        elif not sufficient and "failed_sources" in missing:
            action = "expand_retrieval"
        elif not sufficient and "business_data" in missing:
            action = "expand_retrieval"

        return ContextQuality(
            completeness=round(completeness, 3),
            coverage=round(coverage, 3),
            confidence=round(confidence, 3),
            freshness=round(freshness, 3),
            relevance=round(relevance, 3),
            token_size=tokens,
            sufficient=sufficient,
            missing=missing,
            action=action,
        )

    def _needs_entity(self, ctx: PlatformContext) -> bool:
        q = (ctx.question or "").lower()
        return any(w in q for w in ("this", "that", "current", "blocked", "why is", "approve"))

    def expansion_plan(self, ctx: PlatformContext, quality: ContextQuality) -> RetrievalPlan | None:
        if quality.action != "expand_retrieval":
            return None
        sources = [
            RetrievalSource(source_type="memory", tool="memory", method="search", priority=1),
            RetrievalSource(source_type="graph", tool="graph", method="traverse", priority=2),
            RetrievalSource(source_type="bridge", tool="agent", method="context", priority=3),
        ]
        if ctx.world_state and ctx.world_state.screen and ctx.world_state.screen.entity_id:
            sources.insert(0, RetrievalSource(source_type="bridge", tool="invoice", method="context", priority=0))
        return RetrievalPlan(
            sources=sources,
            query=ctx.question,
            module_hints=["expand"],
            plan_reason="quality_expand",
        )


context_quality_evaluator = ContextQualityEvaluator()
