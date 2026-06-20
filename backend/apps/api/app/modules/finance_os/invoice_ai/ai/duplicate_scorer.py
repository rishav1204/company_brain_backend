from __future__ import annotations

from typing import Any


def weighted_duplicate_score(
    *,
    invoice_number_match: bool,
    vendor_match: bool,
    amount_delta_pct: float,
    date_delta_days: int | None,
    embedding_similarity: float = 0.0,
) -> tuple[float, dict[str, Any]]:
    breakdown: dict[str, Any] = {
        "invoice_number_match": invoice_number_match,
        "vendor_match": vendor_match,
        "amount_delta_pct": amount_delta_pct,
        "date_delta_days": date_delta_days,
        "embedding_similarity": embedding_similarity,
    }
    score = 0.0
    if invoice_number_match:
        score += 40
    if vendor_match:
        score += 25
    if amount_delta_pct <= 0.01:
        score += 25
    elif amount_delta_pct <= 0.05:
        score += 15
    if date_delta_days is not None and date_delta_days <= 7:
        score += 10
    score += embedding_similarity * 5
    breakdown["total"] = round(min(100.0, score), 2)
    return min(100.0, score), breakdown


def classify_duplicate_status(score: float) -> str:
    if score >= 90:
        return "confirmed"
    if score >= 60:
        return "suspected"
    return "clean"
