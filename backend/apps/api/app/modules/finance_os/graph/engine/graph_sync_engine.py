from __future__ import annotations

from app.services.graph_service import upsert_graph_event


def apply_mutations(org_id: str, mutations: dict) -> dict:
    nodes_applied = 0
    edges_applied = 0
    errors: list[str] = []

    for node in mutations.get("nodes") or []:
        label = node.get("label")
        node_id = node.get("id")
        if not label or not node_id:
            continue
        result = upsert_graph_event(org_id=org_id, node_type=label, node_id=str(node_id))
        if result.get("status") == "error":
            errors.append(str(result.get("detail")))
        else:
            nodes_applied += 1

    for edge in mutations.get("edges") or []:
        from_label = edge.get("from_label")
        from_id = edge.get("from_id")
        rel = edge.get("rel_type")
        to_label = edge.get("to_label")
        to_id = edge.get("to_id")
        if not all([from_label, from_id, rel, to_label, to_id]):
            continue
        upsert_graph_event(org_id=org_id, node_type=from_label, node_id=str(from_id))
        upsert_graph_event(org_id=org_id, node_type=to_label, node_id=str(to_id))
        result = upsert_graph_event(
            org_id=org_id,
            node_type=from_label,
            node_id=str(from_id),
            relation=rel,
            target_id=str(to_id),
            to_label=to_label,
        )
        if result.get("relationship_status") == "error":
            errors.append(str(result.get("detail")))
        else:
            edges_applied += 1

    return {
        "nodes_applied": nodes_applied,
        "edges_applied": edges_applied,
        "errors": errors,
        "status": "ok" if not errors else "partial",
    }
