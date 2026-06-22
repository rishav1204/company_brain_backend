from __future__ import annotations

from typing import Any

from app.modules.platform.billing.constants import PLAN_FEATURES, PLAN_INCLUDED_CREDITS, PLAN_LIMITS
from app.modules.platform.billing.repositories.billing_repository import billing_repository


class PlanService:
    def list_plans(self) -> list[dict[str, Any]]:
        rows = billing_repository.list_plans()
        if rows:
            return rows
        return [
            {
                "plan_key": k,
                "name": k.replace("_", " ").title(),
                "tier": i + 1,
                "monthly_price_inr": 0,
                "included_ai_credits": PLAN_INCLUDED_CREDITS.get(k, 0),
                "status": "active",
            }
            for i, k in enumerate(PLAN_FEATURES.keys())
        ]

    def get_plan_features(self, plan_key: str) -> set[str]:
        db_features = billing_repository.get_plan_features(plan_key)
        if db_features:
            return set(db_features)
        return set(PLAN_FEATURES.get(plan_key, frozenset()))

    def get_plan_limit(self, plan_key: str, limit_code: str) -> int | None:
        limits = billing_repository.get_plan_limits(plan_key)
        if limits:
            return limits.get(limit_code)
        return PLAN_LIMITS.get(plan_key, {}).get(limit_code)


plan_service = PlanService()
