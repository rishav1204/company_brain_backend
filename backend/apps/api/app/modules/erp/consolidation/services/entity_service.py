from __future__ import annotations

from typing import Any

from app.modules.erp.consolidation.repositories.hierarchy_repository import hierarchy_repository


class EntityService:
    def list_hierarchy(self, org_id: str) -> list[dict[str, Any]]:
        return hierarchy_repository.list_for_org(org_id)

    def build_tree(self, org_id: str) -> list[dict[str, Any]]:
        rows = hierarchy_repository.list_for_org(org_id)
        children_map: dict[str, list[dict]] = {}
        for row in rows:
            parent = str(row.get("parent_company_id") or "")
            children_map.setdefault(parent, []).append(
                {
                    "company_id": row.get("child_company_id"),
                    "ownership_percent": float(row.get("ownership_percent") or 100),
                }
            )
        roots = {str(r.get("parent_company_id")) for r in rows} - {str(r.get("child_company_id")) for r in rows}
        return [{"company_id": root, "children": children_map.get(root, [])} for root in sorted(roots)]

    def link_entities(
        self,
        org_id: str,
        *,
        parent_company_id: str,
        child_company_id: str,
        ownership_percent: float,
    ) -> dict[str, Any]:
        if parent_company_id == child_company_id:
            raise ValueError("Parent and child company must differ")
        existing = hierarchy_repository.list_for_org(org_id)
        if _would_create_cycle(existing, parent_company_id, child_company_id):
            raise ValueError("Hierarchy cycle detected")
        return hierarchy_repository.upsert(
            org_id,
            parent_company_id=parent_company_id,
            child_company_id=child_company_id,
            ownership_percent=ownership_percent,
        )


def _would_create_cycle(rows: list[dict], parent_id: str, child_id: str) -> bool:
    graph: dict[str, list[str]] = {}
    for row in rows:
        p = str(row.get("parent_company_id") or "")
        c = str(row.get("child_company_id") or "")
        graph.setdefault(p, []).append(c)
    graph.setdefault(parent_id, []).append(child_id)

    def reachable(start: str, target: str, visited: set[str]) -> bool:
        if start == target:
            return True
        if start in visited:
            return False
        visited.add(start)
        return any(reachable(n, target, visited) for n in graph.get(start, []))

    return reachable(child_id, parent_id, set())


entity_service = EntityService()
