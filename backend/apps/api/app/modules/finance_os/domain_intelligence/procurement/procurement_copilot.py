from __future__ import annotations

from app.modules.finance_os.domain_intelligence.procurement.vendor_recommender import recommend_vendors


def answer_query(org_id: str, *, query: str) -> dict:
    hint = query.replace("which vendor", "").replace("best pricing", "").strip()
    vendors = recommend_vendors(org_id, item_hint=hint, limit=3)
    return {"query": query, "recommendations": vendors, "disclaimer": "AI recommendation only"}
