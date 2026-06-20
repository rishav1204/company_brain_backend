from __future__ import annotations

from app.modules.finance_os.graph.engine.dependency_engine import get_dependents


def analyze_dependencies(org_id: str, entity_id: str) -> dict:
    deps = get_dependents(org_id, entity_id)
    return {"entity_id": entity_id, "risk_score": min(len(deps.get("dependents", [])) * 0.1, 1.0), **deps}
