from __future__ import annotations

from app.modules.erp.reconciliation.services.bank_match_service import bank_match_service
from app.modules.erp.reconciliation.services.exception_service import exception_service
from app.modules.erp.reconciliation.services.reconciliation_service import reconciliation_service


def run_reconciliation_scan(org_id: str) -> dict:
    workbench = bank_match_service.list_workbench(org_id)
    unreconciled_count = len(workbench.get("unreconciled") or [])
    suggestions = reconciliation_service.run_daily_suggestions(org_id)
    exceptions = exception_service.list(org_id, status="open")
    return {
        "unreconciled_count": unreconciled_count,
        **suggestions,
        "open_exceptions": len(exceptions),
    }
