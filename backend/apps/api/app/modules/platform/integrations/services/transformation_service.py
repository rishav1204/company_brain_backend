from __future__ import annotations

from app.modules.platform.integrations.adapters.canonical_models import (
    CanonicalBankTransaction,
    CanonicalGSTReturn,
    CanonicalInvoice,
    CanonicalJournal,
    CanonicalPayment,
    CanonicalVendor,
)


class TransformationService:
    """
    Single place to normalize provider payloads into canonical entities.
    Provider-specific mapping lives in `transforms/*` and connector adapters.
    """

    def as_vendor(self, payload: dict) -> CanonicalVendor:
        return CanonicalVendor(name=str(payload.get("name") or ""), raw=payload)

    def as_invoice(self, payload: dict) -> CanonicalInvoice:
        return CanonicalInvoice(invoice_number=str(payload.get("invoice_number") or ""), raw=payload)

    def as_payment(self, payload: dict) -> CanonicalPayment:
        return CanonicalPayment(payment_id=str(payload.get("payment_id") or ""), amount=float(payload.get("amount") or 0), raw=payload)

    def as_journal(self, payload: dict) -> CanonicalJournal:
        return CanonicalJournal(journal_id=str(payload.get("journal_id") or ""), raw=payload)

    def as_bank_tx(self, payload: dict) -> CanonicalBankTransaction:
        return CanonicalBankTransaction(bank_tx_id=str(payload.get("bank_tx_id") or ""), amount=float(payload.get("amount") or 0), raw=payload)

    def as_gst_return(self, payload: dict) -> CanonicalGSTReturn:
        return CanonicalGSTReturn(return_period=str(payload.get("return_period") or ""), raw=payload)


transformation_service = TransformationService()

