from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.modules.platform.billing.services.billing_guard import BillingCheckRequest, billing_guard
from app.modules.platform.billing.services.credit_service import credit_service


@contextmanager
def billing_ai_operation(
    org_id: str,
    *,
    feature: str,
    operation_code: str,
    credit_amount: float | None = None,
) -> Iterator[None]:
    billing_guard.check(
        BillingCheckRequest(
            org_id=org_id,
            feature=feature,
            operation_code=operation_code,
            credit_amount=credit_amount,
        )
    )
    try:
        yield
        credit_service.commit_deduction(org_id, operation_code, amount=credit_amount)
    except Exception:
        raise


def gate_ai_event(org_id: str, *, feature: str, operation_code: str) -> bool:
    """Returns False when billing denies (caller should skip pipeline)."""
    try:
        billing_guard.check(
            BillingCheckRequest(
                org_id=org_id,
                feature=feature,
                operation_code=operation_code,
                skip_credits=True,
            )
        )
        return True
    except Exception:
        return False
