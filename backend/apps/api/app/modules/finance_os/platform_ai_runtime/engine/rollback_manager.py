from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec


class RollbackManager:
    def build_undo_graph(self, graph: ExecutionGraph, *, steps: int = 1) -> ExecutionGraph:
        completed = [n for n in graph.nodes.values() if n.status == "completed" and n.compensation_tool]
        completed.sort(key=lambda n: n.id, reverse=True)
        undo = ExecutionGraph()
        for i, node in enumerate(completed[:steps]):
            if not node.compensation_tool:
                continue
            parts = node.compensation_tool.split(".", 1)
            tool = parts[0] if len(parts) == 2 else "erp"
            method = parts[1] if len(parts) == 2 else node.compensation_tool
            undo.add_node(GraphNodeSpec(
                id=f"undo_{i + 1}",
                tool=tool,
                method=method,
                label=f"Undo {node.label}",
                params={"reverses_node": node.id, **node.params},
                requires_approval=True,
            ))
        return undo

    def record_compensation_chain(self, graph: ExecutionGraph) -> list[dict]:
        chain: list[dict] = []
        for node in graph.nodes.values():
            if node.compensation_tool:
                chain.append({"node_id": node.id, "compensation": node.compensation_tool})
        return chain

    def forensics_context(self, org_id: str, *, entity_type: str, entity_id: str) -> dict:
        try:
            from app.modules.platform.governance.services.forensics_service import forensics_service

            return forensics_service.rollback_analysis(org_id, entity_type=entity_type, entity_id=entity_id)
        except Exception as exc:
            return {"available": False, "detail": str(exc)}

    def enrich_undo_plan(self, org_id: str, graph: ExecutionGraph, undo_graph: ExecutionGraph) -> list[dict]:
        chain = self.record_compensation_chain(graph)
        for node in undo_graph.nodes.values():
            eid = node.params.get("entity_id") or node.params.get("po_id") or node.params.get("grn_id")
            if eid:
                node.params["forensics"] = self.forensics_context(
                    org_id, entity_type=node.tool, entity_id=str(eid),
                )
        return chain


rollback_manager = RollbackManager()
