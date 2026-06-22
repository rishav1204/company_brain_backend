from __future__ import annotations

from typing import Any

from app.modules.platform.billing.constants import DEFAULT_PLAN_KEY, PLAN_INCLUDED_CREDITS
from app.modules.platform.billing.repositories.billing_repository import billing_repository


class SubscriptionService:
    def get_subscription(self, org_id: str) -> dict[str, Any] | None:
        return billing_repository.get_org_subscription(org_id)

    def get_plan_key(self, org_id: str) -> str:
        sub = self.get_subscription(org_id)
        if sub:
            return str(sub["plan_key"])
        return DEFAULT_PLAN_KEY

    def assign_plan(self, org_id: str, plan_key: str, *, status: str = "active") -> dict[str, Any]:
        row = billing_repository.upsert_org_subscription(org_id, plan_key=plan_key, status=status)
        included = PLAN_INCLUDED_CREDITS.get(plan_key, 0)
        if billing_repository.schema_ready():
            from app.modules.platform.billing.services.credit_service import credit_service

            credit_service.ensure_wallet(org_id, included_monthly=float(included))
        return row

    def bootstrap_org(self, org_id: str, plan_key: str | None = None) -> dict[str, Any]:
        key = plan_key or DEFAULT_PLAN_KEY
        return self.assign_plan(org_id, key)


subscription_service = SubscriptionService()
