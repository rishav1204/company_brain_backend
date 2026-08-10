from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

from app.core.config import settings
from app.modules.platform.billing.services.billing_guard import BillingCheckRequest, billing_guard
from app.modules.platform.billing.services.credit_service import credit_service
from app.modules.platform.billing.exceptions import BillingDenied, InsufficientCredits, QuotaExceeded
from app.services.logger import log_event

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def _billing_org_ready(org_id: object) -> bool:
    if not isinstance(org_id, str):
        return False
    return bool(_UUID_RE.match(org_id.strip()))


@contextmanager
def billing_ai_operation(
    org_id: str,
    *,
    feature: str,
    operation_code: str,
    credit_amount: float | None = None,
    skip_credits: bool = False,
) -> Iterator[None]:
    if not _billing_org_ready(org_id):
        yield
        return
    try:
        billing_guard.check(
            BillingCheckRequest(
                org_id=org_id,
                feature=feature,
                operation_code=operation_code,
                credit_amount=credit_amount,
                skip_credits=skip_credits,
            )
        )
    except (BillingDenied, InsufficientCredits, QuotaExceeded):
        raise
    except Exception as exc:
        log_event("billing.guard.failed", org_id=org_id, feature=feature, operation_code=operation_code, detail=str(exc))
        if not settings.billing_fail_open_ai:
            raise
    try:
        yield
    except Exception:
        raise
    else:
        if not skip_credits and _billing_org_ready(org_id):
            credit_service.commit_deduction(org_id, operation_code, amount=credit_amount)


def gate_ai_event(org_id: str, *, feature: str, operation_code: str) -> bool:
    """Returns False when billing denies (caller should skip pipeline)."""
    if not _billing_org_ready(org_id):
        return True
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
    except (BillingDenied, InsufficientCredits, QuotaExceeded):
        return False
    except Exception as exc:
        log_event("billing.gate_ai_event.failed", org_id=org_id, feature=feature, operation_code=operation_code, detail=str(exc))
        if not settings.billing_fail_open_ai:
            raise
        return False
