from __future__ import annotations

from app.services.neo4j_service import neo4j_service


def format_neighbors(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        lines.append(
            f"{row.get('from_label')}:{row.get('from_id')} -> {row.get('rel_type')} -> "
            f"{row.get('to_label')}:{row.get('to_id')}"
        )
    return lines


def format_lineage_paths(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        rels = row.get("rel_types") or []
        rel_chain = " -> ".join(str(r) for r in rels) if rels else "RELATED"
        lines.append(
            f"{row.get('start_label')}:{row.get('start_id')} --[{rel_chain}]--> "
            f"{row.get('end_label')}:{row.get('end_id')}"
        )
    return lines


def get_lifecycle(org_id: str, entity_id: str, *, direction: str = "both", max_depth: int = 6) -> dict:
    rows = neo4j_service.traverse_lineage(org_id, entity_id, direction=direction, max_depth=max_depth)
    return {
        "entity_id": entity_id,
        "paths": format_lineage_paths(rows),
        "raw": rows,
        "count": len(rows),
    }
