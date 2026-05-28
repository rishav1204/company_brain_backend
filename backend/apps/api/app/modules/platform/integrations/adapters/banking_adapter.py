from __future__ import annotations

from typing import Protocol

from app.modules.platform.integrations.adapters.canonical_models import CanonicalBankTransaction


class BankingAdapter(Protocol):
    def to_canonical_bank_transaction(self, payload: dict) -> CanonicalBankTransaction: ...

