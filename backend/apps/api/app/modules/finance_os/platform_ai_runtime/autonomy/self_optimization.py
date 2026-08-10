"""Self-optimization — safer plans, fewer redundant LLM/retrieval calls (Wave 5).

Never changes accounting correctness; only plan structure & reuse.
"""

from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, PlanMetadata
from app.modules.finance_os.platform_ai_runtime.tools.catalog_read import READ_SPECS
from app.modules.finance_os.platform_ai_runtime.tools.catalog_draft import DRAFT_SPECS

_READ_KEYS = {f"{s.tool}.{s.method}" for s in READ_SPECS}
_MUTATE_KEYS = {f"{s.tool}.{s.method}" for s in DRAFT_SPECS if not s.read_only}


class SelfOptimizationEngine:
    def optimize(
        self,
        graph: ExecutionGraph,
        meta: PlanMetadata,
        *,
        context_preloaded: bool = False,
        learning_hints: list[str] | None = None,
        prep_only: bool = False,
    ) -> tuple[ExecutionGraph, PlanMetadata, list[str]]:
        notes: list[str] = []
        nodes = list(graph.nodes.values())
        if not nodes:
            return graph, meta, notes

        # 1. Drop redundant memory/graph retrieval when platform context already filled
        if context_preloaded:
            keep = [
                n
                for n in nodes
                if not (
                    (n.tool == "memory" and n.method == "search")
                    or (n.tool == "graph" and n.method == "traverse")
                )
            ]
            if len(keep) < len(nodes):
                notes.append("skipped_redundant_retrieval")
                nodes = keep or nodes[:1]

        # 2. Mark independent consecutive read nodes as parallel_group
        read_nodes = [n for n in nodes if f"{n.tool}.{n.method}" in _READ_KEYS and not n.depends_on]
        if len(read_nodes) >= 2:
            for n in read_nodes:
                n.parallel_group = "wave_reads"
            notes.append("parallelized_independent_reads")

        # 3. Prep-only: force mutating draft nodes requires_approval + prep_only flag
        if prep_only:
            for n in nodes:
                key = f"{n.tool}.{n.method}"
                if key in _MUTATE_KEYS or n.requires_approval:
                    n.prep_only = True
                    n.requires_approval = True
            notes.append("prep_only_mutations_gated")
            meta = meta.model_copy(update={"prep_only": True})

        # 4. Batch similar sequential same-tool reads (keep first, skip dups)
        seen_tools: set[str] = set()
        deduped: list[GraphNodeSpec] = []
        for n in nodes:
            key = f"{n.tool}.{n.method}"
            if key in _READ_KEYS and key in seen_tools and not n.depends_on:
                notes.append(f"deduped_tool:{key}")
                continue
            if key in _READ_KEYS:
                seen_tools.add(key)
            deduped.append(n)
        nodes = deduped

        # 5. Learning hints: prefer batching when approval bottlenecks known
        if learning_hints and any("batch_approval" in h for h in learning_hints):
            notes.append("batch_approval_prep_hint")
            meta = meta.model_copy(
                update={
                    "collaboration_message": (meta.collaboration_message or "")
                    + " Grouping approval-bound prep steps for human review."
                }
            )

        # Rebuild graph preserving dependency IDs that still exist
        id_set = {n.id for n in nodes}
        for n in nodes:
            n.depends_on = [d for d in (n.depends_on or []) if d in id_set]
        new_graph = ExecutionGraph(nodes=nodes)
        notes.append(f"node_count={len(nodes)}")
        meta = meta.model_copy(
            update={
                "estimated_steps": len(nodes),
                "optimization_notes": list(meta.optimization_notes or []) + notes,
            }
        )
        return new_graph, meta, notes


self_optimization_engine = SelfOptimizationEngine()
