from __future__ import annotations

from app.modules.erp.query_services import intel_reads


def analyze_spend(org_id: str) -> dict:
    pos = intel_reads.list_purchase_orders(org_id, limit=500)
    by_vendor: dict[str, float] = {}
    total = 0.0
    for po in pos:
        vid = str(po.get("vendor_id") or "unknown")
        amt = float(po.get("total_amount") or 0)
        by_vendor[vid] = by_vendor.get(vid, 0) + amt
        total += amt
    top_vendors = sorted(by_vendor.items(), key=lambda x: x[1], reverse=True)[:10]
    concentration = (top_vendors[0][1] / total * 100) if top_vendors and total else 0
    return {
        "total_spend": round(total, 2),
        "po_count": len(pos),
        "top_vendors": [{"vendor_id": v, "amount": round(a, 2)} for v, a in top_vendors],
        "vendor_concentration_pct": round(concentration, 2),
    }
