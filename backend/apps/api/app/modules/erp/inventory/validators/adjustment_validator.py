from __future__ import annotations


def validate_adjustment_amount(*, value_variance: float) -> None:
    if value_variance != value_variance:
        raise ValueError("Invalid adjustment value")
