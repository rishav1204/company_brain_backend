"""M27 read bridge for treasury modules."""

from __future__ import annotations

from app.modules.finance_os.memory.engine.retrieval_engine import search


def treasury_context(org_id: str, query: str = "liquidity treasury risk") -> list[dict]:
    return search(org_id, query, memory_type="treasury", top_k=5)
