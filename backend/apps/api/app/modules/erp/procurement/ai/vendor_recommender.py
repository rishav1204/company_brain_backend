from __future__ import annotations

from app.modules.erp.procurement.services.vendor_selection_service import vendor_selection_service


def recommend_vendors(org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]:
    return vendor_selection_service.recommend(org_id, item_hint=item_hint, limit=limit)
