from __future__ import annotations

from typing import Any


def build_ic_eliminations(
    balances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate elimination lines for matched intercompany due-to/due-from pairs."""
    eliminations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for bal in balances:
        src = str(bal.get("source_company_id") or "")
        tgt = str(bal.get("target_company_id") or "")
        if not src or not tgt:
            continue
        key = tuple(sorted([src, tgt]))
        if key in seen:
            continue
        seen.add(key)
        amount = float(bal.get("amount") or 0)
        if abs(amount) < 0.01:
            continue
        eliminations.append(
            {
                "elimination_type": "intercompany_balance",
                "source_company_id": src,
                "target_company_id": tgt,
                "debit_amount": amount if amount > 0 else 0,
                "credit_amount": abs(amount) if amount < 0 else 0,
                "description": f"Eliminate IC balance {src} -> {tgt}",
            }
        )
    return eliminations


def build_ic_transaction_eliminations(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    eliminations: list[dict[str, Any]] = []
    for tx in transactions:
        if str(tx.get("status")) != "matched":
            continue
        amt = float(tx.get("amount") or 0)
        if amt <= 0:
            continue
        eliminations.append(
            {
                "elimination_type": "intercompany_transaction",
                "source_company_id": tx.get("source_company_id"),
                "target_company_id": tx.get("target_company_id"),
                "debit_amount": amt,
                "credit_amount": amt,
                "description": f"Eliminate IC {tx.get('transaction_type')} {tx.get('id')}",
            }
        )
    return eliminations
