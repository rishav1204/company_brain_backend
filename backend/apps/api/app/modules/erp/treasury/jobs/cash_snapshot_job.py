from __future__ import annotations

from app.modules.erp.treasury.services.cash_position_service import cash_position_service


def run_cash_snapshot(org_id: str, *, bank_account_id: str | None = None) -> dict:
    if bank_account_id:
        cash_position_service.snapshot_account(org_id, bank_account_id=bank_account_id)
    else:
        cash_position_service.snapshot_all(org_id)
    position = cash_position_service.refresh_and_emit(org_id)
    return {"snapshots": "ok", "available_cash": position.get("available_cash")}
