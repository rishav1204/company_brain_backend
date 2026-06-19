from __future__ import annotations

from app.modules.erp.assets.engine.account_resolver import (
    resolve_accumulated_depreciation_account,
    resolve_depreciation_expense_account,
    resolve_fixed_asset_account,
    resolve_gain_on_disposal_account,
    resolve_loss_on_disposal_account,
)


def build_depreciation_lines(
    org_id: str,
    *,
    amount: float,
    depreciation_expense_account_id: str | None = None,
    accumulated_depreciation_account_id: str | None = None,
) -> list[dict]:
    if amount <= 0:
        raise ValueError("Depreciation amount must be positive")
    expense_id = depreciation_expense_account_id or resolve_depreciation_expense_account(org_id)
    accum_id = accumulated_depreciation_account_id or resolve_accumulated_depreciation_account(org_id)
    if not expense_id or not accum_id:
        raise ValueError("Depreciation expense and accumulated depreciation accounts required")
    return [
        {"account_id": expense_id, "debit_amount": amount, "credit_amount": 0, "line_description": "Depreciation expense"},
        {"account_id": accum_id, "debit_amount": 0, "credit_amount": amount, "line_description": "Accumulated depreciation"},
    ]


def build_capitalization_lines(
    org_id: str,
    *,
    cost: float,
    fixed_asset_account_id: str | None,
    credit_account_id: str,
) -> list[dict]:
    fa_id = fixed_asset_account_id or resolve_fixed_asset_account(org_id)
    if not fa_id:
        raise ValueError("Fixed asset account required")
    if not credit_account_id:
        raise ValueError("Credit account required for capitalization")
    return [
        {"account_id": fa_id, "debit_amount": cost, "credit_amount": 0, "line_description": "Fixed asset capitalization"},
        {"account_id": credit_account_id, "debit_amount": 0, "credit_amount": cost, "line_description": "Capitalization credit"},
    ]


def compute_gain_loss(*, sale_amount: float, book_value: float) -> float:
    return round(sale_amount - book_value, 2)


def build_disposal_lines(
    org_id: str,
    *,
    cost: float,
    accumulated_depreciation: float,
    book_value: float,
    sale_amount: float,
    fixed_asset_account_id: str | None = None,
    accumulated_depreciation_account_id: str | None = None,
    bank_account_id: str | None = None,
) -> list[dict]:
    fa_id = fixed_asset_account_id or resolve_fixed_asset_account(org_id)
    accum_id = accumulated_depreciation_account_id or resolve_accumulated_depreciation_account(org_id)
    if not fa_id or not accum_id:
        raise ValueError("Fixed asset and accumulated depreciation accounts required")
    gain_loss = compute_gain_loss(sale_amount=sale_amount, book_value=book_value)
    lines: list[dict] = []
    if sale_amount > 0 and bank_account_id:
        lines.append({
            "account_id": bank_account_id,
            "debit_amount": sale_amount,
            "credit_amount": 0,
            "line_description": "Proceeds on disposal",
        })
    if accumulated_depreciation > 0:
        lines.append({
            "account_id": accum_id,
            "debit_amount": accumulated_depreciation,
            "credit_amount": 0,
            "line_description": "Clear accumulated depreciation",
        })
    if gain_loss < 0:
        loss_id = resolve_loss_on_disposal_account(org_id)
        if not loss_id:
            raise ValueError("Loss on disposal account required")
        lines.append({
            "account_id": loss_id,
            "debit_amount": abs(gain_loss),
            "credit_amount": 0,
            "line_description": "Loss on disposal",
        })
    lines.append({
        "account_id": fa_id,
        "debit_amount": 0,
        "credit_amount": cost,
        "line_description": "Remove fixed asset cost",
    })
    if gain_loss > 0:
        gain_id = resolve_gain_on_disposal_account(org_id)
        if not gain_id:
            raise ValueError("Gain on disposal account required")
        lines.append({
            "account_id": gain_id,
            "debit_amount": 0,
            "credit_amount": gain_loss,
            "line_description": "Gain on disposal",
        })
    return lines


def build_impairment_lines(
    org_id: str,
    *,
    impairment_amount: float,
    fixed_asset_account_id: str | None = None,
    impairment_expense_account_id: str | None = None,
) -> list[dict]:
    from app.modules.erp.assets.engine.account_resolver import resolve_impairment_expense_account

    fa_id = fixed_asset_account_id or resolve_fixed_asset_account(org_id)
    exp_id = impairment_expense_account_id or resolve_impairment_expense_account(org_id)
    if not fa_id or not exp_id:
        raise ValueError("Fixed asset and impairment expense accounts required")
    return [
        {"account_id": exp_id, "debit_amount": impairment_amount, "credit_amount": 0, "line_description": "Impairment expense"},
        {"account_id": fa_id, "debit_amount": 0, "credit_amount": impairment_amount, "line_description": "Asset impairment"},
    ]
