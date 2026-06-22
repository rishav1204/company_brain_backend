from __future__ import annotations

from datetime import date

from app.modules.platform.billing.exceptions import QuotaExceeded
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.subscription_service import subscription_service
from app.modules.platform.billing.services.plan_service import plan_service


class UsageService:
    _LIVE_COUNTERS = {
        "users": billing_repository.count_org_users,
        "entities": billing_repository.count_org_entities,
        "gstins": billing_repository.count_org_gstins,
    }

    def current_usage(self, org_id: str, metric_code: str) -> int:
        if metric_code in self._LIVE_COUNTERS:
            try:
                return self._LIVE_COUNTERS[metric_code](org_id)
            except Exception:
                return 0
        return billing_repository.get_usage_metric(org_id, metric_code)

    def get_limit(self, org_id: str, limit_code: str) -> int | None:
        plan_key = subscription_service.get_plan_key(org_id)
        return plan_service.get_plan_limit(plan_key, limit_code)

    def check_quota(self, org_id: str, limit_code: str, *, increment: int = 0) -> None:
        limit = self.get_limit(org_id, limit_code)
        if limit is None:
            return
        metric_map = {
            "max_users": "users",
            "max_entities": "entities",
            "max_gstins": "gstins",
            "invoices_monthly": "invoices",
            "api_calls_monthly": "api_calls",
            "workflow_runs_monthly": "workflow_runs",
        }
        metric = metric_map.get(limit_code, limit_code)
        current = self.current_usage(org_id, metric) + increment
        if current > limit:
            raise QuotaExceeded(limit_code, current, limit)

    def record(self, org_id: str, metric_code: str, *, delta: int = 1, **kwargs) -> None:
        if not billing_repository.schema_ready():
            return
        billing_repository.record_usage_event(
            org_id,
            metric_code=metric_code,
            delta=delta,
            reference_type=kwargs.get("reference_type"),
            reference_id=kwargs.get("reference_id"),
            metadata=kwargs.get("metadata"),
        )

    def usage_summary(self, org_id: str) -> dict:
        plan_key = subscription_service.get_plan_key(org_id)
        limits = {
            "max_users": self.get_limit(org_id, "max_users"),
            "max_entities": self.get_limit(org_id, "max_entities"),
            "max_gstins": self.get_limit(org_id, "max_gstins"),
            "api_calls_monthly": self.get_limit(org_id, "api_calls_monthly"),
        }
        usage = {
            "users": self.current_usage(org_id, "users"),
            "entities": self.current_usage(org_id, "entities"),
            "gstins": self.current_usage(org_id, "gstins"),
            "api_calls": self.current_usage(org_id, "api_calls"),
            "invoices": self.current_usage(org_id, "invoices"),
            "workflow_runs": self.current_usage(org_id, "workflow_runs"),
        }
        return {"plan_key": plan_key, "limits": limits, "usage": usage, "period_start": date.today().replace(day=1).isoformat()}


usage_service = UsageService()
