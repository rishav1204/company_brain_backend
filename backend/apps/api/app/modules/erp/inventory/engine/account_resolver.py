from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_code, resolve_account_by_type


def resolve_inventory_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "1400") or resolve_account_by_type(org_id, "inventory")


def resolve_grni_clearing_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "1401") or resolve_account_by_type(org_id, "grni_clearing")


def resolve_cogs_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "5100") or resolve_account_by_type(org_id, "cogs")


def resolve_inventory_loss_account(org_id: str) -> str | None:
    return resolve_account_by_code(org_id, "5101") or resolve_account_by_type(org_id, "inventory_loss")
