from __future__ import annotations

from app.modules.erp.reconciliation.services.reconciliation_service import reconciliation_service


def run_auto_match(org_id: str, *, bank_account_id: str | None = None) -> dict:
    if bank_account_id:
        return reconciliation_service.suggest_for_account(org_id, bank_account_id=bank_account_id)
    return reconciliation_service.run_daily_suggestions(org_id)
