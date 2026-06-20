from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import format_neighbors
from app.modules.finance_os.graph.engine.causality_engine import explain_chain
from app.services.neo4j_service import neo4j_service


def build_context(org_id: str, entity_id: str) -> str:
    neighbors = neo4j_service.get_entity_neighbors(org_id, entity_id)
    lines = format_neighbors(neighbors)
    chain = explain_chain(org_id, entity_id)
    explanation = chain.get("explanation") or []
    if isinstance(explanation, list):
        lines.extend(explanation)
    elif explanation:
        lines.append(str(explanation))
    return "\n".join(lines)
