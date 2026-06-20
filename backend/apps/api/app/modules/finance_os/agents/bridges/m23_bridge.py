from __future__ import annotations

from app.modules.finance_os.memory.bridges.reconciliation_bridge import reconciliation_context


def match_context(org_id: str, bank_account_id: str | None) -> dict:
    hits = reconciliation_context(org_id, bank_account_id=bank_account_id)
    return {"bank_account_id": bank_account_id, "memory_hits": len(hits)}
