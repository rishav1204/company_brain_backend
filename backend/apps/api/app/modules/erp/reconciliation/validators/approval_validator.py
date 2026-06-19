from __future__ import annotations


ALLOWED_APPROVE = {"suggested", "pending_approval", "manual_review", "partially_matched"}
ALLOWED_REJECT = {"suggested", "pending_approval", "manual_review", "exception"}


def validate_approve_status(current_status: str) -> None:
    if current_status not in ALLOWED_APPROVE:
        raise ValueError(f"Cannot approve reconciliation in status {current_status}")


def validate_reject_status(current_status: str) -> None:
    if current_status not in ALLOWED_REJECT:
        raise ValueError(f"Cannot reject reconciliation in status {current_status}")
