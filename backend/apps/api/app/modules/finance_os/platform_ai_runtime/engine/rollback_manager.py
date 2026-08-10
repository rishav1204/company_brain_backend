from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.engine.compensation_engine import compensation_engine
from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec
from app.services.logger import log_event


class RollbackManager:
    def build_undo_graph(self, graph: ExecutionGraph, *, steps: int = 1) -> ExecutionGraph:
        """Build compensating graph only — never destructive delete; always requires approval (AI-05/06)."""
        compensation_engine.attach_missing_compensations(graph)
        completed = [
            n
            for n in graph.nodes.values()
            if n.status == "completed" and (n.compensation_tool or compensation_engine.compensation_for(n.tool, n.method))
        ]
        completed.sort(key=lambda n: n.id, reverse=True)
        undo = ExecutionGraph()
        for i, node in enumerate(completed[:steps]):
            if not node.compensation_tool:
                node.compensation_tool = compensation_engine.compensation_for(node.tool, node.method)
            comp_node = compensation_engine.resolve_compensation_node(node)
            if not comp_node:
                continue
            comp_node.id = f"undo_{i + 1}"
            comp_node.label = f"Compensate {node.label or node.id}"
            comp_node.requires_approval = True
            # Strip forensics-only props from tool params path if nested
            undo.add_node(comp_node)
        return undo

    def record_compensation_chain(self, graph: ExecutionGraph) -> list[dict]:
        return compensation_engine.build_chain(graph)

    def forensics_context(self, org_id: str, *, entity_type: str, entity_id: str) -> dict:
        """Advisory only — forensics failure must not block undo (AI-06)."""
        try:
            from app.modules.platform.governance.services.forensics_service import forensics_service

            result = forensics_service.rollback_analysis(org_id, entity_type=entity_type, entity_id=entity_id)
            if not isinstance(result, dict):
                return {"available": True, "detail": result}
            return {**result, "available": result.get("available", True)}
        except Exception as exc:
            log_event(
                "m38.rollback.forensics_unavailable",
                org_id=org_id,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=str(exc),
            )
            return {"available": False, "advisory_only": True, "detail": str(exc)}

    def enrich_undo_plan(self, org_id: str, graph: ExecutionGraph, undo_graph: ExecutionGraph) -> list[dict]:
        chain = self.record_compensation_chain(graph)
        for node in undo_graph.nodes.values():
            eid = (
                node.params.get("entity_id")
                or node.params.get("po_id")
                or node.params.get("grn_id")
                or node.params.get("invoice_id")
                or node.params.get("journal_id")
            )
            if eid:
                # Attach under metadata key that tools ignore if unknown kwargs are stripped
                node.params.setdefault("_forensics_advisory", self.forensics_context(
                    org_id, entity_type=node.tool, entity_id=str(eid),
                ))
        return chain


rollback_manager = RollbackManager()
