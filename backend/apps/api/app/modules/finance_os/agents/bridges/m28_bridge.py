from __future__ import annotations

from app.services.logger import log_event


def lineage(org_id: str, entity_id: str) -> list[dict]:
    if not entity_id:
        return []
    try:
        from app.modules.finance_os.graph.services.lineage_service import lineage as graph_lineage

        result = graph_lineage(org_id, entity_id, max_depth=4)
        paths = result.get("paths") or result.get("trace") or []
        return paths if isinstance(paths, list) else [result]
    except Exception as exc:
        log_event("graph.bridge.lineage_failed", org_id=org_id, entity_id=entity_id, error=str(exc))
        return []
