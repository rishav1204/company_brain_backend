from __future__ import annotations

from app.modules.erp.assets.engine.depreciation_engine import compute_depreciation


def validate_capitalization(*, cost: float, useful_life_months: int, threshold: float) -> None:
    if cost <= 0:
        raise ValueError("Asset cost must be positive")
    if useful_life_months <= 0:
        raise ValueError("Useful life must be positive")
    if cost < threshold:
        raise ValueError(f"Asset cost below capitalization threshold ({threshold})")


def validate_depreciation_run(*, status: str, book_value: float, salvage_value: float) -> None:
    if book_value <= salvage_value:
        raise ValueError("Asset fully depreciated")


def validate_disposal(*, sale_amount: float) -> None:
    if sale_amount < 0:
        raise ValueError("Sale amount cannot be negative")


def validate_impairment(*, impairment_amount: float, book_value: float) -> None:
    if impairment_amount <= 0:
        raise ValueError("Impairment amount must be positive")
    if impairment_amount > book_value:
        raise ValueError("Impairment cannot exceed book value")


def preview_depreciation(
    *,
    cost: float,
    salvage_value: float,
    useful_life_months: int,
    accumulated_depreciation: float,
    book_value: float,
    method: str,
) -> float:
    return compute_depreciation(
        cost=cost,
        salvage_value=salvage_value,
        useful_life_months=useful_life_months,
        accumulated_depreciation=accumulated_depreciation,
        book_value=book_value,
        method=method,
    )
