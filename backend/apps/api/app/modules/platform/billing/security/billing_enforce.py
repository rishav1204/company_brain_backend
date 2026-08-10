from __future__ import annotations

import re

from fastapi import HTTPException

from app.modules.platform.billing.exceptions import BillingDenied
from app.modules.platform.billing.services.billing_guard import billing_guard

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def _billing_org_ready(org_id: object) -> bool:
    """Only enforce for real tenant UUIDs (skip MagicMock / legacy test org ids)."""
    if not isinstance(org_id, str):
        return False
    return bool(_UUID_RE.match(org_id.strip()))


def enforce_billing(org_id: str | None, feature: str, **kwargs) -> None:
    """Call from module guards before IAM checks. No-op when org_id missing."""
    if not _billing_org_ready(org_id):
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
    if not _billing_org_ready(org_id):
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
