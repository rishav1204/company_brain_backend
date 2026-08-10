"""Compensation resolution for M38 mutating tools (Phase 8 Wave 2 / AI-05)."""

from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec
from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry


# Tools that intentionally have no safe automated reverse (money movement / irreversible ERP).
IRREVERSIBLE_HINTS: set[tuple[str, str]] = {
    ("fiscal", "init_close"),
    ("tax_gst", "submit_return"),
    ("procurement", "confirm_grn"),
    ("inventory", "receive"),
    ("assets", "create"),
    ("assets", "submit"),
}


class CompensationEngine:
    def compensation_for(self, tool: str, method: str) -> str | None:
        return tool_registry.compensation_for(tool, method)

    def is_reversible(self, tool: str, method: str) -> bool:
        key = (str(tool).lower(), str(method).lower())
        if key in IRREVERSIBLE_HINTS:
            return False
        return bool(self.compensation_for(tool, method))

    def resolve_compensation_node(self, node: GraphNodeSpec) -> GraphNodeSpec | None:
        comp = node.compensation_tool or self.compensation_for(node.tool, node.method)
        if not comp or "." not in comp:
            return None
        tool, method = comp.split(".", 1)
        params = dict(node.params or {})
        # Map common entity id aliases into compensation required keys.
        if "entity_id" in params:
            if method in {"cancel_po", "cancel"} and tool == "procurement" and "po_id" not in params:
                params.setdefault("po_id", params["entity_id"])
            if method in {"cancel_grn", "cancel"} and tool == "procurement" and "grn_id" not in params:
                params.setdefault("grn_id", params["entity_id"])
            if method in {"cancel_invoice", "cancel"} and tool == "ap" and "invoice_id" not in params:
                params.setdefault("invoice_id", params["entity_id"])
            if method in {"void_draft", "cancel"} and tool == "journals" and "journal_id" not in params:
                params.setdefault("journal_id", params["entity_id"])
            if method in {"deactivate_item"} and "item_id" not in params:
                params.setdefault("item_id", params["entity_id"])
            if method in {"cancel_claim", "cancel"} and tool == "expenses" and "claim_id" not in params:
                params.setdefault("claim_id", params["entity_id"])
        params["reverses_node"] = node.id
        return GraphNodeSpec(
            id=f"comp_{node.id}",
            tool=tool,
            method=method,
            label=f"Compensate {node.label or node.id}",
            params=params,
            requires_approval=True,
        )

    def attach_missing_compensations(self, graph: ExecutionGraph) -> ExecutionGraph:
        """Fill compensation_tool on nodes from registry when planner omitted it."""
        for node in graph.nodes.values():
            if node.compensation_tool:
                continue
            if tool_registry.is_read_only(node.tool, node.method):
                continue
            comp = self.compensation_for(node.tool, node.method)
            if comp:
                node.compensation_tool = comp
        return graph

    def build_chain(self, graph: ExecutionGraph) -> list[dict]:
        chain: list[dict] = []
        for node in graph.nodes.values():
            if node.status != "completed":
                continue
            comp = node.compensation_tool or self.compensation_for(node.tool, node.method)
            chain.append(
                {
                    "node_id": node.id,
                    "tool": node.tool,
                    "method": node.method,
                    "compensation": comp,
                    "reversible": bool(comp),
                }
            )
        return chain


compensation_engine = CompensationEngine()
