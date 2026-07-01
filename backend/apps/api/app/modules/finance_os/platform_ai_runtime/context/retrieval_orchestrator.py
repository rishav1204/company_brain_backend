from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.modules.finance_os.agents.services import context_service
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ResolvedEntity,
    RetrievalPlan,
    RetrievalSource,
)
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState
from app.modules.finance_os.platform_ai_runtime.services.executor import executor
from app.services.logger import log_event
from app.services.retrieval_service import retrieve_context


def _primary_entity(entities: list[ResolvedEntity]) -> tuple[str | None, str | None]:
    for e in entities:
        if e.entity_id:
            return e.entity_type, e.entity_id
    if entities:
        return entities[0].entity_type, entities[0].entity_id
    return None, None


def _build_payload(world_state: WorldState | None, entities: list[ResolvedEntity], query: str) -> dict:
    payload: dict = {"query": query}
    etype, eid = _primary_entity(entities)
    if world_state and world_state.screen:
        if world_state.screen.entity_type:
            payload["entity_type"] = world_state.screen.entity_type
        if world_state.screen.entity_id:
            payload["entity_id"] = world_state.screen.entity_id
            payload["invoice_id"] = world_state.screen.entity_id
    if etype and not payload.get("entity_type"):
        payload["entity_type"] = etype
    if eid and not payload.get("entity_id"):
        payload["entity_id"] = eid
    if world_state and world_state.org and world_state.org.fiscal_period_id:
        payload["period_id"] = world_state.org.fiscal_period_id
    if world_state and world_state.selection:
        payload.update({k: v for k, v in world_state.selection.items() if v})
    return payload


class RetrievalOrchestrator:
    def fetch(
        self,
        org_id: str,
        *,
        plan: RetrievalPlan,
        world_state: WorldState | None,
        entities: list[ResolvedEntity],
        user_id: str = "platform_context",
        roles: list[str] | None = None,
    ) -> dict:
        payload = _build_payload(world_state, entities, plan.query)
        etype, eid = _primary_entity(entities)
        memory: list[dict] = []
        graph: list[dict] = []
        erp_facts: dict = {}
        documents: list[dict] = []
        policies: list[dict] = []
        trace: list[dict] = []

        def run_source(source: RetrievalSource) -> tuple[str, object]:
            try:
                if source.source_type == "memory" or (source.tool == "memory" and source.method == "search"):
                    from app.modules.finance_os.agents.bridges import m27_bridge

                    hits = m27_bridge.search(
                        org_id,
                        plan.query,
                        entity_type=etype,
                        entity_id=eid,
                        top_k=15,
                    )
                    return "memory", hits
                if source.source_type == "graph" or (source.tool == "graph" and source.method == "traverse"):
                    from app.modules.finance_os.agents.bridges import m28_bridge

                    target = eid or (world_state.screen.entity_id if world_state and world_state.screen else None)
                    paths = m28_bridge.lineage(org_id, target) if target else []
                    return "graph", paths if isinstance(paths, list) else [paths] if paths else []
                if source.source_type == "bridge" and source.tool == "agent":
                    ctx = context_service.build(org_id, "platform_runtime", payload)
                    return "agent_context", ctx
                if source.source_type == "bridge" and source.tool == "invoice":
                    from app.modules.finance_os.agents.bridges import m25_bridge

                    inv_id = payload.get("entity_id") or payload.get("invoice_id") or ""
                    return "invoice", m25_bridge.invoice_context(org_id, str(inv_id))
                if source.source_type == "bridge" and source.tool == "gst":
                    from app.modules.finance_os.agents.bridges import m21_bridge

                    return "gst", m21_bridge.compliance_context(org_id, str(eid or ""))
                if source.source_type == "documents" or source.tool == "documents":
                    contexts, citations = retrieve_context(org_id, plan.query, subject_ref=eid, top_k=8)
                    docs = [
                        {"content": c, "citation": cit.model_dump() if hasattr(cit, "model_dump") else cit}
                        for c, cit in zip(contexts, citations)
                    ]
                    return "documents", docs
                if source.source_type == "erp" and source.tool and source.method:
                    result = executor.run(
                        org_id,
                        tool=source.tool,
                        method=source.method,
                        params={**source.params, "query": plan.query},
                        actor_id=user_id,
                        roles=roles,
                        human_approved=True,
                    )
                    return f"erp:{source.tool}.{source.method}", result
            except Exception as exc:
                log_event("m38.context.retrieval_failed", source=source.source_type, detail=str(exc))
                return source.source_type, {}
            return source.source_type, {}

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(run_source, s): s for s in plan.sources}
            for fut in as_completed(futures):
                source = futures[fut]
                key, data = fut.result()
                trace.append({"source": key, "tool": source.tool, "method": source.method, "ok": bool(data)})
                if key == "memory" and isinstance(data, list):
                    memory.extend(data)
                elif key == "graph" and isinstance(data, list):
                    graph.extend(data)
                elif key == "documents" and isinstance(data, list):
                    documents.extend(data)
                elif key == "agent_context":
                    ctx = data
                    if hasattr(ctx, "memory_snippets"):
                        memory.extend(ctx.memory_snippets or [])
                    if hasattr(ctx, "graph_paths"):
                        graph.extend(ctx.graph_paths or [])
                    if hasattr(ctx, "erp_facts"):
                        erp_facts.update(ctx.erp_facts or {})
                    if hasattr(ctx, "policy_flags"):
                        policies.extend(ctx.policy_flags or [])
                elif key.startswith("erp:"):
                    erp_facts[key] = data
                elif key in {"invoice", "gst"}:
                    erp_facts[key] = data

        return {
            "memory": memory,
            "graph": graph,
            "erp_facts": erp_facts,
            "documents": documents,
            "policies": policies,
            "retrieval_trace": trace,
        }


retrieval_orchestrator = RetrievalOrchestrator()
