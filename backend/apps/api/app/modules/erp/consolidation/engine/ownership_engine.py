from __future__ import annotations


def compute_ownership_split(*, subsidiary_profit: float, ownership_percent: float) -> dict[str, float]:
    pct = max(0.0, min(float(ownership_percent), 100.0))
    parent_share = round(float(subsidiary_profit) * pct / 100.0, 2)
    minority = round(float(subsidiary_profit) - parent_share, 2)
    return {
        "ownership_percent": pct,
        "parent_share": parent_share,
        "minority_interest": minority,
    }


def aggregate_subsidiary_profits(entity_balances: dict[str, float]) -> list[dict]:
    return [{"company_id": cid, "profit": amt} for cid, amt in entity_balances.items()]
