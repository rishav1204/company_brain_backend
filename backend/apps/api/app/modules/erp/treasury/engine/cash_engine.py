from __future__ import annotations

from app.modules.erp.treasury.engine.cash_position_engine import (
    build_position,
    compute_available_cash,
    compute_net_liquidity,
)


def compute_closing_balance(*, opening_balance: float, inflows: float, outflows: float) -> float:
    return round(float(opening_balance) + float(inflows) - float(outflows), 2)


def build_account_snapshot(
    *,
    bank_account_id: str,
    account_name: str,
    opening_balance: float,
    inflows: float,
    outflows: float,
    restricted: float = 0,
) -> dict:
    closing = compute_closing_balance(opening_balance=opening_balance, inflows=inflows, outflows=outflows)
    available = compute_available_cash(credits=inflows, debits=outflows, restricted=restricted)
    return {
        "bank_account_id": bank_account_id,
        "account_name": account_name,
        "opening_balance": round(opening_balance, 2),
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "closing_balance": closing,
        "available": available,
    }


__all__ = ["compute_closing_balance", "build_account_snapshot", "build_position", "compute_available_cash", "compute_net_liquidity"]
