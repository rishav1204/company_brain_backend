from __future__ import annotations

from dataclasses import dataclass

from app.modules.platform.billing.exceptions import BillingDenied
from app.modules.platform.billing.services.entitlement_service import entitlement_service
from app.modules.platform.billing.services.usage_service import usage_service
from app.modules.platform.billing.services.credit_service import credit_service


@dataclass
class BillingCheckRequest:
    org_id: str
    feature: str | None = None
    limit_code: str | None = None
    operation_code: str | None = None
    credit_amount: float | None = None
    skip_credits: bool = False


class BillingGuard:
    def check(self, req: BillingCheckRequest | str, *, feature: str | None = None, **kwargs) -> None:
        if isinstance(req, str):
            req = BillingCheckRequest(org_id=req, feature=feature, **kwargs)
        if req.feature:
            entitlement_service.require_feature(req.org_id, req.feature)
        if req.limit_code:
            usage_service.check_quota(req.org_id, req.limit_code)
        if req.operation_code and not req.skip_credits:
            credit_service.reserve_credits(
                req.org_id,
                req.operation_code,
                amount=req.credit_amount,
            )

    def check_feature(self, org_id: str, feature: str) -> None:
        self.check(BillingCheckRequest(org_id=org_id, feature=feature))

    def check_ai_operation(
        self,
        org_id: str,
        *,
        feature: str,
        operation_code: str,
        credit_amount: float | None = None,
    ) -> None:
        self.check(
            BillingCheckRequest(
                org_id=org_id,
                feature=feature,
                operation_code=operation_code,
                credit_amount=credit_amount,
            )
        )


billing_guard = BillingGuard()
