from __future__ import annotations


def monthly_straight_line(*, cost: float, salvage_value: float, useful_life_months: int) -> float:
    if useful_life_months <= 0:
        return 0.0
    depreciable = max(0.0, cost - salvage_value)
    return round(depreciable / useful_life_months, 2)


def compute_depreciation(
    *,
    cost: float,
    salvage_value: float,
    useful_life_months: int,
    accumulated_depreciation: float,
    book_value: float,
    method: str = "straight_line",
) -> float:
    if method != "straight_line":
        raise ValueError(f"Unsupported depreciation method: {method}")
    if book_value <= salvage_value:
        return 0.0
    monthly = monthly_straight_line(cost=cost, salvage_value=salvage_value, useful_life_months=useful_life_months)
    remaining = book_value - salvage_value
    return round(min(monthly, remaining), 2)


def period_key_from_date(depreciation_date: str) -> str:
    return str(depreciation_date or "")[:7]
