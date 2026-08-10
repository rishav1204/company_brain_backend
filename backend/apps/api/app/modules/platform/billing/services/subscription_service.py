from __future__ import annotations

from typing import Any

from app.modules.platform.billing.constants import DEFAULT_PLAN_KEY
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.plan_service import plan_service


class SubscriptionService:
    def get_subscription(self, org_id: str) -> dict[str, Any] | None:
        return billing_repository.get_org_subscription(org_id)

    def get_plan_key(self, org_id: str) -> str:
        sub = self.get_subscription(org_id)
        if sub:
            return str(sub["plan_key"])
        return DEFAULT_PLAN_KEY

    def assign_plan(self, org_id: str, plan_key: str, *, status: str = "active") -> dict[str, Any]:
        plan = plan_service.get_plan(plan_key)
        if plan and str(plan.get("status") or "active") == "deprecated":
            raise ValueError(f"Cannot assign deprecated plan: {plan_key}")
        row = billing_repository.upsert_org_subscription(org_id, plan_key=plan_key, status=status)
        try:
            from app.services.cache.api_quota_cache import invalidate_plan_limit

            invalidate_plan_limit(org_id)
        except Exception:
            pass
        included = plan_service.get_included_ai_credits(plan_key)
        if billing_repository.schema_ready():
            from app.modules.platform.billing.services.credit_service import credit_service

            credit_service.ensure_wallet(org_id, included_monthly=float(included))
            billing_repository.sync_wallet_included_monthly(org_id, float(included))
        return row

    def bootstrap_org(self, org_id: str, plan_key: str | None = None) -> dict[str, Any]:
        key = plan_key or DEFAULT_PLAN_KEY
        return self.assign_plan(org_id, key)


subscription_service = SubscriptionService()
