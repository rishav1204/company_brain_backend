from __future__ import annotations

EDITABLE_STATUSES = {"draft"}
ISSUABLE_STATUSES = {"draft"}
CANCELLABLE_STATUSES = {"draft", "issued", "overdue"}


class InvoiceValidator:
    def validate_amounts(self, *, subtotal: float, gst_amount: float, total_amount: float) -> None:
        if total_amount <= 0:
            raise ValueError("Total amount must be positive")
        if round(subtotal + gst_amount, 2) != round(total_amount, 2):
            raise ValueError("subtotal + gst_amount must equal total_amount")

    def validate_gst_calculation(self, *, taxable_value: float, gst_rate: float, gst_amount: float) -> None:
        expected = round(taxable_value * gst_rate, 2)
        if abs(expected - gst_amount) > 0.05:
            raise ValueError(f"GST amount {gst_amount} does not match taxable_value × rate ({expected})")

    def ensure_editable(self, status: str) -> None:
        if status not in EDITABLE_STATUSES:
            raise ValueError(f"Invoice not editable in status '{status}'")

    def ensure_issuable(self, status: str) -> None:
        if status not in ISSUABLE_STATUSES:
            raise ValueError(f"Invoice cannot be issued in status '{status}'")

    def ensure_cancellable(self, status: str) -> None:
        if status not in CANCELLABLE_STATUSES:
            raise ValueError(f"Invoice cannot be cancelled in status '{status}'")


invoice_validator = InvoiceValidator()
