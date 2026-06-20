from __future__ import annotations

from app.services.neo4j_service import neo4j_service


def get_dependents(org_id: str, entity_id: str, *, max_depth: int = 4) -> dict:
    rows = neo4j_service.traverse_dependencies(org_id, entity_id, max_depth=max_depth)
    dependents = [
        f"{row.get('dependent_label')}:{row.get('dependent_id')}"
        for row in rows
    ]
    return {"entity_id": entity_id, "dependents": dependents, "raw": rows, "count": len(dependents)}
