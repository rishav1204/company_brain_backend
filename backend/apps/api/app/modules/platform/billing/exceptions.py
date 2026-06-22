from __future__ import annotations


class BillingDenied(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 402,
        code: str = "billing_denied",
        upgrade_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.upgrade_required = upgrade_required


class FeatureNotEntitled(BillingDenied):
    def __init__(self, feature_code: str, plan_key: str | None = None) -> None:
        msg = f"Feature '{feature_code}' not included in your plan"
        if plan_key:
            msg += f" ({plan_key})"
        super().__init__(msg, status_code=402, code="feature_not_entitled", upgrade_required=True)
        self.feature_code = feature_code
        self.plan_key = plan_key


class QuotaExceeded(BillingDenied):
    def __init__(self, limit_code: str, current: int, limit: int) -> None:
        super().__init__(
            f"Quota exceeded for {limit_code}: {current}/{limit}",
            status_code=429,
            code="quota_exceeded",
        )
        self.limit_code = limit_code
        self.current = current
        self.limit = limit


class InsufficientCredits(BillingDenied):
    def __init__(self, required: float, balance: float) -> None:
        super().__init__(
            f"Insufficient AI credits: need {required}, have {balance}",
            status_code=402,
            code="insufficient_credits",
            upgrade_required=True,
        )
        self.required = required
        self.balance = balance
