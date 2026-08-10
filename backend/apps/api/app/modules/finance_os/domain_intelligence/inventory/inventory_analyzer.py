from __future__ import annotations

from app.modules.erp.query_services import intel_reads


def analyze(org_id: str, *, query: str) -> dict:
    balances = intel_reads.list_stock_balances(org_id, limit=2000)
    items = {str(i["id"]): i for i in intel_reads.list_items(org_id, limit=2000)}
    total_value = round(sum(float(b.get("inventory_value") or 0) for b in balances), 2)
    sku_count = len({str(b.get("item_id")) for b in balances})
    dead_stock = [
        {
            "item_id": b.get("item_id"),
            "warehouse_id": b.get("warehouse_id"),
            "quantity": b.get("quantity_on_hand"),
            "value": b.get("inventory_value"),
            "item_code": (items.get(str(b.get("item_id"))) or {}).get("item_code"),
        }
        for b in balances
        if float(b.get("quantity_on_hand") or 0) > 0 and float(b.get("inventory_value") or 0) <= 0
    ]
    return {
        "org_id": org_id,
        "query": query,
        "summary": f"{sku_count} SKUs tracked; inventory book value {total_value}",
        "metrics": {
            "total_skus": sku_count,
            "total_value": total_value,
            "dead_stock_candidates": len(dead_stock),
        },
        "dead_stock": dead_stock[:20],
    }
