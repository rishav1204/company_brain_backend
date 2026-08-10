from __future__ import annotations

from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts


def suggest_accounts_for_journal(extracted_data: dict) -> list[dict]:
    """Journal-module wrapper around document intelligence ledger suggester."""
    return suggest_ledger_accounts(extracted_data)
