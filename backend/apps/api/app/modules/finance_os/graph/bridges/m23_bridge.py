from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import get_lifecycle


def reconciliation_lineage(org_id: str, bank_transaction_id: str) -> dict:
    return get_lifecycle(org_id, bank_transaction_id, direction="both", max_depth=5)
