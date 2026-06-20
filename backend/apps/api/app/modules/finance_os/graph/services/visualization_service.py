from __future__ import annotations

from app.modules.finance_os.graph.services.finance_graph_service import get_entity


def visualization(org_id: str, entity_id: str) -> dict:
    data = get_entity(org_id, entity_id)
    nodes = {entity_id: {"id": entity_id, "label": "Entity"}}
    edges = []
    for n in data.get("neighbors") or []:
        to_id = n.get("to_id")
        if to_id:
            nodes[str(to_id)] = {"id": to_id, "label": n.get("to_label")}
        edges.append(
            {
                "from": n.get("from_id"),
                "to": n.get("to_id"),
                "type": n.get("rel_type"),
            }
        )
    return {"nodes": list(nodes.values()), "edges": edges}
