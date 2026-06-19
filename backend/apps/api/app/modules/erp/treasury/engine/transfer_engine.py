from __future__ import annotations


def validate_transfer(*, source_account_id: str, destination_account_id: str, amount: float) -> None:
    if source_account_id == destination_account_id:
        raise ValueError("Source and destination accounts must differ")
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")


def approval_roles_for_amount(amount: float) -> list[str]:
    roles = ["finance_manager"]
    if amount >= 50_000:
        roles.append("controller")
    if amount >= 500_000:
        roles.append("cfo")
    return roles


def preview_journal_accounts(*, source_ledger_id: str, dest_ledger_id: str, amount: float) -> list[dict]:
    return [
        {"account_id": dest_ledger_id, "debit_amount": amount, "credit_amount": 0, "description": "Transfer in"},
        {"account_id": source_ledger_id, "debit_amount": 0, "credit_amount": amount, "description": "Transfer out"},
    ]
