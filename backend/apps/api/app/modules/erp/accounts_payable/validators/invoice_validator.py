from __future__ import annotations

import hashlib

INVOICE_STATUSES = {
    "draft",
    "pending_review",
    "pending_approval",
    "approved",
    "partially_paid",
    "paid",
    "cancelled",
}

EDITABLE_STATUSES = {"draft", "pending_review"}
APPROVABLE_STATUSES = {"pending_approval", "pending_review"}


def build_duplicate_checksum(*, vendor_id: str, invoice_number: str, total_amount: float, invoice_date: str) -> str:
    raw = f"{vendor_id}|{invoice_number.strip().upper()}|{total_amount:.2f}|{invoice_date}"
    return hashlib.sha256(raw.encode()).hexdigest()


class InvoiceValidator:
    def validate_status(self, status: str) -> None:
        if status not in INVOICE_STATUSES:
            raise ValueError(f"Invalid invoice status: {status}")

    def ensure_editable(self, status: str) -> None:
        if status not in EDITABLE_STATUSES:
            raise ValueError(f"Invoice status '{status}' is not editable")

    def ensure_approvable(self, status: str) -> None:
        if status not in APPROVABLE_STATUSES:
            raise ValueError(f"Invoice cannot be approved in status '{status}'")

    def validate_amounts(self, *, invoice_amount: float, gst_amount: float, total_amount: float) -> None:
        if invoice_amount < 0 or gst_amount < 0 or total_amount <= 0:
            raise ValueError("Invoice amounts must be positive")
        expected = round(invoice_amount + gst_amount, 2)
        if round(total_amount, 2) != expected:
            raise ValueError(f"total_amount must equal invoice_amount + gst_amount (got {total_amount}, expected {expected})")


invoice_validator = InvoiceValidator()
