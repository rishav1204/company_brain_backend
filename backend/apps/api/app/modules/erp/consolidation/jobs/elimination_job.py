from __future__ import annotations

from app.modules.erp.consolidation.engine import elimination_engine
from app.modules.erp.consolidation.repositories.intercompany_repository import intercompany_repository


def refresh_elimination_preview(org_id: str) -> list[dict]:
    balances = intercompany_repository.list_balances(org_id)
    txs = intercompany_repository.list_transactions(org_id, status="matched")
    lines = elimination_engine.build_ic_eliminations(balances)
    lines.extend(elimination_engine.build_ic_transaction_eliminations(txs))
    return lines
