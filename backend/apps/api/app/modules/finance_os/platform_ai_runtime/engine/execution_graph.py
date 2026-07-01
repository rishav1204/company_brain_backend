from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec


class ExecutionGraph:
    def __init__(self, nodes: list[GraphNodeSpec] | None = None, edges: list[dict] | None = None) -> None:
        self.nodes: dict[str, GraphNodeSpec] = {n.id: n for n in (nodes or [])}
        self.edges: list[dict] = edges or []

    def add_node(self, node: GraphNodeSpec) -> None:
        self.nodes[node.id] = node

    def mark_complete(self, node_id: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = "completed"

    def mark_failed(self, node_id: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = "failed"

    def mark_running(self, node_id: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = "running"

    def mark_skipped(self, node_id: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = "skipped"

    def _deps_satisfied(self, node: GraphNodeSpec) -> bool:
        if not node.depends_on:
            return True
        return all(self.nodes[d].status == "completed" for d in node.depends_on if d in self.nodes)

    def next_ready_node(self) -> GraphNodeSpec | None:
        for node in self.nodes.values():
            if node.status == "pending" and self._deps_satisfied(node):
                return node
        return None

    def all_complete(self) -> bool:
        if not self.nodes:
            return True
        return all(n.status in {"completed", "skipped"} for n in self.nodes.values())

    def has_failed(self) -> bool:
        return any(n.status == "failed" for n in self.nodes.values())

    def pending_approval_nodes(self) -> list[GraphNodeSpec]:
        return [n for n in self.nodes.values() if n.status == "pending" and n.requires_approval]

    def to_dict(self) -> dict:
        return {
            "nodes": [n.model_dump() for n in self.nodes.values()],
            "edges": self.edges,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionGraph:
        nodes = [GraphNodeSpec(**n) for n in data.get("nodes") or []]
        return cls(nodes=nodes, edges=data.get("edges") or [])
