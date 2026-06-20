from __future__ import annotations

from typing import Any


def score_ledger_match(
    *,
    account_code: str | None,
    account_name: str | None,
    vendor_history_account: str | None,
    retrieval_score: float,
) -> float:
    score = retrieval_score * 0.5
    if vendor_history_account and account_code and vendor_history_account == account_code:
        score += 0.35
    if account_name:
        score += 0.05
    return min(1.0, score)


def suggest_from_patterns(
    patterns: list[dict[str, Any]],
    vendor_account: str | None = None,
) -> dict[str, Any] | None:
    if not patterns and not vendor_account:
        return None
    best: dict[str, Any] | None = None
    best_score = 0.0
    for p in patterns:
        meta = p.get("metadata") or {}
        account_id = meta.get("account_id") or meta.get("suggested_account_id")
        account_code = meta.get("account_code")
        score = float(p.get("score") or 0)
        final = score_ledger_match(
            account_code=account_code,
            account_name=meta.get("account_name"),
            vendor_history_account=vendor_account,
            retrieval_score=score,
        )
        if final > best_score:
            best_score = final
            best = {
                "suggested_account_id": account_id,
                "account_code": account_code,
                "confidence_score": final,
                "source": "retrieval",
            }
    if vendor_account and (not best or best_score < 0.6):
        return {
            "suggested_account_id": None,
            "account_code": vendor_account,
            "confidence_score": 0.65,
            "source": "vendor_history",
        }
    return best
