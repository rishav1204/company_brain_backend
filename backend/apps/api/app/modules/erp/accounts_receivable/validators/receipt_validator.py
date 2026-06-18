from __future__ import annotations

PAYMENT_MODES = {"bank_transfer", "upi", "cash", "cheque", "card", "gateway"}


class ReceiptValidator:
    def validate_mode(self, mode: str) -> None:
        if mode not in PAYMENT_MODES:
            raise ValueError(f"Invalid payment mode: {mode}")

    def ensure_completable(self, status: str) -> None:
        if status not in {"recorded", "processing"}:
            raise ValueError(f"Receipt cannot be completed in status '{status}'")


receipt_validator = ReceiptValidator()
