from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_code, resolve_account_by_type, resolve_expense_account


def resolve_fixed_asset_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "1500") or resolve_account_by_type(org_id, "fixed_asset")


def resolve_accumulated_depreciation_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "1501") or resolve_account_by_type(org_id, "accumulated_depreciation")


def resolve_depreciation_expense_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "6200") or resolve_account_by_type(org_id, "depreciation")


def resolve_gain_on_disposal_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "4200") or resolve_account_by_type(org_id, "revenue")


def resolve_loss_on_disposal_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "6201") or resolve_account_by_type(org_id, "expense")


def resolve_impairment_expense_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "6202") or resolve_account_by_type(org_id, "expense")


def resolve_capitalization_credit_account(org_id: str, *, reclass_from_expense: bool = False) -> str | None:
    if reclass_from_expense:
        return resolve_expense_account(org_id)
    return resolve_account_by_code(org_id, "1100") or resolve_account_by_type(org_id, "bank")
