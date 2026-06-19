from __future__ import annotations


def compute_available_cash(*, credits: float, debits: float, restricted: float = 0) -> float:
    return round(max(0.0, float(credits) - float(debits) - float(restricted)), 2)


def compute_net_liquidity(
    *,
    available_cash: float,
    expected_collections: float,
    upcoming_payments: float,
) -> float:
    return round(available_cash + expected_collections - upcoming_payments, 2)


def build_position(
    *,
    accounts: list[dict],
    expected_collections: float,
    upcoming_payments: float,
    restricted_cash: float = 0,
) -> dict:
    total_available = sum(float(a.get("available") or 0) for a in accounts)
    return {
        "available_cash": round(total_available, 2),
        "restricted_cash": round(restricted_cash, 2),
        "expected_collections": round(expected_collections, 2),
        "upcoming_payments": round(upcoming_payments, 2),
        "net_liquidity": compute_net_liquidity(
            available_cash=total_available,
            expected_collections=expected_collections,
            upcoming_payments=upcoming_payments,
        ),
        "accounts": accounts,
    }
