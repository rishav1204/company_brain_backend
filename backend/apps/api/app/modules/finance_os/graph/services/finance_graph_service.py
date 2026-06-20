from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import format_neighbors
from app.services.neo4j_service import neo4j_service


def get_entity(org_id: str, entity_id: str) -> dict:
    neighbors = neo4j_service.get_entity_neighbors(org_id, entity_id)
    return {
        "entity_id": entity_id,
        "neighbors": neighbors,
        "trace": format_neighbors(neighbors),
        "count": len(neighbors),
    }
