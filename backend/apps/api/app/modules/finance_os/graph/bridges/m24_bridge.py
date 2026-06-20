from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import get_lifecycle


def cash_chain(org_id: str, payment_id: str) -> dict:
    return get_lifecycle(org_id, payment_id, direction="out", max_depth=6)
