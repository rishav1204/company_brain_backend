from __future__ import annotations

from app.modules.erp.query_services import intel_reads


def recommend_vendors(org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]:
    return intel_reads.recommend_vendors(org_id, item_hint=item_hint, limit=limit)
