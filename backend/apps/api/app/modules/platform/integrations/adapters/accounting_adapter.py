from __future__ import annotations

from typing import Protocol

from app.modules.platform.integrations.adapters.canonical_models import CanonicalInvoice, CanonicalJournal, CanonicalVendor


class AccountingAdapter(Protocol):
    def to_canonical_vendor(self, payload: dict) -> CanonicalVendor: ...
    def to_canonical_invoice(self, payload: dict) -> CanonicalInvoice: ...
    def to_canonical_journal(self, payload: dict) -> CanonicalJournal: ...

