from __future__ import annotations

PAYMENT_STATUSES = {"scheduled", "processing", "completed", "failed", "cancelled"}


class PaymentValidator:
    def validate_status(self, status: str) -> None:
        if status not in PAYMENT_STATUSES:
            raise ValueError(f"Invalid payment status: {status}")

    def ensure_schedulable(self, status: str) -> None:
        if status not in {"scheduled"}:
            raise ValueError(f"Payment cannot be scheduled in status '{status}'")

    def ensure_executable(self, status: str) -> None:
        if status not in {"scheduled", "processing"}:
            raise ValueError(f"Payment cannot be executed in status '{status}'")


payment_validator = PaymentValidator()
