from __future__ import annotations


def load_reconciliation(org_id: str) -> dict:
    from app.modules.erp.reconciliation.jobs.reconciliation_scan_job import run_reconciliation_scan

    scan = run_reconciliation_scan(org_id)
    unreconciled = int(scan.get("unreconciled_count") or 0)
    open_exc = int(scan.get("open_exceptions") or 0)
    total = max(unreconciled + open_exc, unreconciled, 1)
    rate = round(max(0.0, (total - unreconciled) / total * 100.0), 2)
    return {
        "unreconciled_count": unreconciled,
        "open_exceptions": open_exc,
        "reconciliation_rate": rate,
    }
