"""M27 read bridge for reconciliation modules."""

from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search


def reconciliation_context(org_id: str, *, bank_account_id: str | None = None, query: str = "reconciliation override") -> list[dict]:
    if bank_account_id:
        return search(org_id, query, memory_type="reconciliation", entity_type="bank_account", entity_id=bank_account_id, top_k=5)
    return search(org_id, query, memory_type="reconciliation", top_k=5)
