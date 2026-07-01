from __future__ import annotations

import json
import re

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, PlanMetadata, WorldState
from app.services.llm_provider import llm_provider
from app.services.logger import log_event


_MUTATING_VERBS = ("create", "buy", "purchase", "submit", "confirm", "receive", "pay", "approve", "capitalize", "post")


def _heuristic_plan(
    message: str,
    world_state: WorldState | None,
    *,
    platform_context: PlatformContext | None = None,
    skip_retrieval_steps: bool = False,
) -> tuple[ExecutionGraph, PlanMetadata]:
    text = message.lower()
    graph = ExecutionGraph()
    approval_points: list[str] = []
    rollback: list[dict] = []

    if any(k in text for k in ("buy", "purchase", "procure", "order")) and any(k in text for k in ("laptop", "item", "inventory", "stock", "widget")):
        graph.add_node(GraphNodeSpec(
            id="step_1", tool="procurement", method="create_po", label="Create purchase order draft",
            requires_approval=True, compensation_tool="procurement.cancel_po",
        ))
        graph.add_node(GraphNodeSpec(
            id="step_2", tool="procurement", method="submit_po", label="Submit PO for approval",
            depends_on=["step_1"], requires_approval=True,
        ))
        graph.add_node(GraphNodeSpec(
            id="step_3", tool="procurement", method="create_grn", label="Create goods receipt",
            depends_on=["step_2"], requires_approval=True,
        ))
        graph.add_node(GraphNodeSpec(
            id="step_4", tool="procurement", method="confirm_grn", label="Confirm GRN → inventory receipt",
            depends_on=["step_3"], requires_approval=True,
        ))
        approval_points = ["step_1", "step_2", "step_3", "step_4"]
        rollback = [
            {"after": "step_1", "compensation": "procurement.cancel_po"},
            {"after": "step_3", "compensation": "procurement.cancel_grn"},
        ]
        reasoning = "Multi-step procurement: PO → submit → GRN → confirm triggers inventory integration."
    elif any(k in text for k in ("receive", "receipt", "stock in")) and "inventory" in text:
        graph.add_node(GraphNodeSpec(
            id="step_1", tool="inventory", method="receive", label="Manual inventory receipt",
            requires_approval=True,
        ))
        approval_points = ["step_1"]
        reasoning = "Direct inventory receipt with unit cost."
    elif any(k in text for k in ("overdue", "collect", "collections")) and any(k in text for k in ("pay", "workflow", "start", "launch")):
        graph.add_node(GraphNodeSpec(id="step_1", tool="ar", method="list_overdue", label="List overdue invoices"))
        graph.add_node(GraphNodeSpec(
            id="step_2", tool="workflow", method="start", label="Launch collection follow-up workflow",
            depends_on=["step_1"], requires_approval=True,
            params={"workflow_key": "COLLECTION_FOLLOWUP"},
        ))
        approval_points = ["step_2"]
        reasoning = "Collections: identify overdue AR then launch workflow."
    elif any(k in text for k in ("overdue", "collect", "collections")):
        graph.add_node(GraphNodeSpec(id="step_1", tool="ar", method="list_overdue", label="List overdue invoices"))
        reasoning = "Read-only collections query."
    elif any(k in text for k in ("close", "period close", "close books")):
        steps = [
            ("step_1", "inventory", "validate_close", "Validate inventory for close", False),
            ("step_2", "reconciliation", "list_exceptions", "Check reconciliation exceptions", False),
            ("step_3", "reconciliation", "list", "Review open reconciliations", False),
            ("step_4", "ap", "list_outstanding", "Review outstanding AP", False),
            ("step_5", "ar", "list_outstanding", "Review outstanding AR", False),
            ("step_6", "treasury", "get_cash_position", "Verify cash position", False),
            ("step_7", "tax_gst", "list_returns", "Review GST return drafts", False),
            ("step_8", "gl", "trial_balance", "Generate trial balance", False),
            ("step_9", "fiscal", "close_checklist", "Run fiscal close checklist", True),
        ]
        prev: str | None = None
        for sid, tool, method, label, needs_approval in steps:
            deps = [prev] if prev else []
            graph.add_node(GraphNodeSpec(
                id=sid, tool=tool, method=method, label=label,
                depends_on=deps, requires_approval=needs_approval,
            ))
            prev = sid
        approval_points = ["step_9"]
        reasoning = "Long-running period close: inventory → recon → AP/AR → treasury → tax → reports → fiscal close."
    elif any(k in text for k in ("balance", "on hand", "stock level")):
        graph.add_node(GraphNodeSpec(id="step_1", tool="inventory", method="list_balances", label="List inventory balances"))
        reasoning = "Read-only inventory balance query."
    elif any(k in text for k in ("invoice", "ap")) and any(k in text for k in ("list", "show", "get")):
        graph.add_node(GraphNodeSpec(id="step_1", tool="ap", method="list_invoices", label="List AP invoices"))
        reasoning = "Read-only AP invoice query."
    elif skip_retrieval_steps or (platform_context and platform_context.summaries):
        reasoning = "Context pre-loaded by Platform Context Engine; no retrieval DAG steps."
    else:
        graph.add_node(GraphNodeSpec(id="step_1", tool="memory", method="search", label="Search organizational memory", params={"query": message}))
        graph.add_node(GraphNodeSpec(
            id="step_2", tool="graph", method="traverse", label="Traverse entity graph",
            depends_on=["step_1"],
            params={"entity_id": (world_state.screen.entity_id if world_state and world_state.screen else "") or ""},
        ))
        reasoning = "Default: retrieve context from memory and graph before acting."

    requires_approval = any(n.requires_approval for n in graph.nodes.values())
    mutating = any(v in text for v in _MUTATING_VERBS)
    confidence = 0.75 if graph.nodes else 0.5
    if platform_context and platform_context.summaries:
        confidence = max(confidence, 0.8)
    if mutating and requires_approval:
        confidence = 0.82
    band = "strong" if confidence >= 0.8 else "review" if confidence >= 0.6 else "manual"
    risk = "medium" if requires_approval else "low"

    meta = PlanMetadata(
        confidence=round(confidence * 100, 2),
        confidence_band=band,
        risk_level=risk,
        reasoning=reasoning,
        estimated_steps=len(graph.nodes),
        approval_points=approval_points,
        rollback_strategy=rollback,
    )
    return graph, meta


def _llm_plan(
    message: str,
    world_state: WorldState | None,
    *,
    platform_context: PlatformContext | None = None,
) -> tuple[ExecutionGraph, PlanMetadata] | None:
    ws = world_state.model_dump() if world_state else {}
    ctx_block = ""
    if platform_context:
        from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler

        ctx_block = f"\nPlatform context:\n{prompt_assembler.build_planner_context_block(platform_context)[:3000]}\n"
    prompt = (
        f"User goal: {message}\nWorld state: {json.dumps(ws)[:1500]}\n{ctx_block}"
        "Return JSON: {\"reasoning\": str, \"nodes\": [{\"id\", \"tool\", \"method\", \"label\", "
        "\"requires_approval\": bool, \"depends_on\": [], \"params\": {}}], "
        "\"rollback_strategy\": [{\"after\", \"compensation\"}]}"
    )
    try:
        raw = llm_provider.generate_json(
            org_id="platform-runtime",
            prompt=prompt,
            system_prompt="You are a finance platform planner. Output strict JSON only. Tools: procurement.*, inventory.*, ap.*, ar.*, workflow.start, memory.search, graph.traverse.",
        )
        text = json.dumps(raw) if isinstance(raw, dict) else str(raw or "").strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group())
        nodes = [GraphNodeSpec(**n) for n in data.get("nodes") or []]
        if not nodes:
            return None
        graph = ExecutionGraph(nodes=nodes)
        approval_points = [n.id for n in nodes if n.requires_approval]
        meta = PlanMetadata(
            confidence=78.0,
            confidence_band="review",
            risk_level="medium" if approval_points else "low",
            reasoning=str(data.get("reasoning") or ""),
            estimated_steps=len(nodes),
            approval_points=approval_points,
            rollback_strategy=data.get("rollback_strategy") or [],
        )
        return graph, meta
    except Exception as exc:
        log_event("m38.planner.llm_failed", detail=str(exc))
        return None


class GoalPlanner:
    def plan(
        self,
        message: str,
        *,
        world_state: WorldState | None = None,
        platform_context: PlatformContext | None = None,
        use_llm: bool = True,
        skip_retrieval_steps: bool = False,
    ) -> tuple[ExecutionGraph, PlanMetadata]:
        if use_llm:
            try:
                if llm_provider.is_ready():
                    llm_result = _llm_plan(message, world_state, platform_context=platform_context)
                    if llm_result:
                        return llm_result
            except Exception:
                pass
        return _heuristic_plan(
            message,
            world_state,
            platform_context=platform_context,
            skip_retrieval_steps=skip_retrieval_steps,
        )


goal_planner = GoalPlanner()
