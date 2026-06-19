from __future__ import annotations

from collections import defaultdict

from app.modules.erp.procurement.repositories.po_repository import po_repository


def detect_anomalies(org_id: str) -> list[dict]:
    pos = po_repository.list(org_id, limit=500)
    by_vendor_day: dict[tuple[str, str], list[float]] = defaultdict(list)
    anomalies: list[dict] = []
    for po in pos:
        key = (str(po.get("vendor_id")), str(po.get("po_date") or "")[:10])
        by_vendor_day[key].append(float(po.get("total_amount") or 0))
    for (vendor_id, day), amounts in by_vendor_day.items():
        if len(amounts) >= 3 and all(a < 50000 for a in amounts):
            anomalies.append({
                "type": "split_purchase",
                "vendor_id": vendor_id,
                "date": day,
                "po_count": len(amounts),
                "total": round(sum(amounts), 2),
            })
    return anomalies
