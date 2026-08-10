from __future__ import annotations

from app.modules.erp.query_services import reconciliation_queries


def load_reconciliation(org_id: str) -> dict:
    scan = reconciliation_queries.run_scan(org_id)
    unreconciled = int(scan.get("unreconciled_count") or 0)
    open_exc = int(scan.get("open_exceptions") or 0)
    total = max(unreconciled + open_exc, unreconciled, 1)
    rate = round(max(0.0, (total - unreconciled) / total * 100.0), 2)
    return {
        "unreconciled_count": unreconciled,
        "open_exceptions": open_exc,
        "reconciliation_rate": rate,
    }
