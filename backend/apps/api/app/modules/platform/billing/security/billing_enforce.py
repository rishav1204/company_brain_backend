from __future__ import annotations

from fastapi import HTTPException

from app.modules.platform.billing.exceptions import BillingDenied
from app.modules.platform.billing.services.billing_guard import billing_guard


def enforce_billing(org_id: str | None, feature: str, **kwargs) -> None:
    """Call from module guards before IAM checks. No-op when org_id missing."""
    if not org_id:
        return
    try:
        billing_guard.check(org_id, feature=feature, **kwargs)
    except BillingDenied as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "upgrade_required": exc.upgrade_required,
            },
        ) from exc


def enforce_ai_billing(
    org_id: str | None,
    *,
    feature: str,
    operation_code: str,
    credit_amount: float | None = None,
) -> None:
    if not org_id:
        return
    try:
        billing_guard.check_ai_operation(
            org_id,
            feature=feature,
            operation_code=operation_code,
            credit_amount=credit_amount,
        )
    except BillingDenied as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "upgrade_required": exc.upgrade_required,
            },
        ) from exc
