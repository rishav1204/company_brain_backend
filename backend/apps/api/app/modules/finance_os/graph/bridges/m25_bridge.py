from __future__ import annotations

from app.modules.finance_os.graph.engine.dependency_engine import get_dependents


def vendor_ecosystem(org_id: str, vendor_id: str) -> dict:
    return get_dependents(org_id, vendor_id)
