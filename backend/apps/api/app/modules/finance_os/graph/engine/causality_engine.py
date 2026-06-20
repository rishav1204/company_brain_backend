from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import format_lineage_paths
from app.services.neo4j_service import neo4j_service


def explain_chain(
    org_id: str,
    entity_id: str,
    *,
    end_label: str = "Compliance",
    max_depth: int = 8,
) -> dict:
    paths = neo4j_service.find_causal_paths(org_id, entity_id, end_label=end_label, max_depth=max_depth)
    if not paths:
        lineage = neo4j_service.traverse_lineage(org_id, entity_id, direction="out", max_depth=5)
        return {
            "entity_id": entity_id,
            "explanation": format_lineage_paths(lineage),
            "paths": [],
            "confidence": 0.6,
        }
    formatted = []
    for p in paths:
        nodes = p.get("path_nodes") or []
        rels = p.get("rel_types") or []
        chain = []
        for i, node in enumerate(nodes):
            chain.append(f"{node.get('label')}:{node.get('id')}")
            if i < len(rels):
                chain.append(f"--{rels[i]}-->")
        formatted.append(" ".join(chain))
    return {
        "entity_id": entity_id,
        "explanation": formatted,
        "paths": paths,
        "confidence": 0.85 if formatted else 0.5,
    }
