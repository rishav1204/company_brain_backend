from __future__ import annotations


def validate_match_request(*, bank_transaction_ids: list[str], allocations: list[dict]) -> None:
    if not bank_transaction_ids:
        raise ValueError("At least one bank transaction required")
    if not allocations:
        raise ValueError("At least one entity allocation required")
    for alloc in allocations:
        if not alloc.get("entity_type") or not alloc.get("entity_id"):
            raise ValueError("Each allocation requires entity_type and entity_id")
        if float(alloc.get("amount") or 0) <= 0:
            raise ValueError("Allocation amount must be positive")


def validate_confidence_for_auto_suggest(confidence_score: float, min_score: float = 0.25) -> bool:
    return confidence_score >= min_score
