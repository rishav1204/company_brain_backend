"""AI budget manager — org/user/goal soft & hard limits (Wave 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.services.cache.redis_cache import get_cached, set_cached
from app.services.logger import log_event

NS = "ai.gateway.budget"


@dataclass
class BudgetStatus:
    allowed: bool
    soft_warning: bool = False
    hard_blocked: bool = False
    reason: str = "ok"
    monthly_used: float = 0.0
    daily_used: float = 0.0
    monthly_limit: float = 0.0
    daily_limit: float = 0.0
    remaining_usd: float = 0.0
    prefer_cheap: bool = False
    prefer_skip_llm: bool = False


class AIBudgetManager:
    """Enforces USD-ish budgets using accumulated cost estimates/actuals.

    Soft limit → prefer_cheap, adaptive planner.
    Hard limit → block new LLM calls (never silent exceed).
    """

    def _limits(self, org_id: str) -> tuple[float, float, float, float]:
        monthly = float(getattr(settings, "ai_monthly_budget_usd", 500.0) or 500.0)
        daily = float(getattr(settings, "ai_daily_budget_usd", 50.0) or 50.0)
        per_user = float(getattr(settings, "ai_user_daily_budget_usd", 20.0) or 20.0)
        per_goal = float(getattr(settings, "ai_goal_budget_usd", 10.0) or 10.0)
        return monthly, daily, per_user, per_goal

    def _day_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def _month_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m")

    def _get(self, org_id: str, key: str) -> float:
        raw = get_cached(org_id, NS, {"k": key})
        if raw is None:
            return 0.0
        try:
            return float(raw.get("used") if isinstance(raw, dict) else raw)
        except Exception:
            return 0.0

    def _set(self, org_id: str, key: str, value: float, ttl: int) -> None:
        set_cached(org_id, NS, {"used": value}, {"k": key}, ttl=ttl)

    def check(
        self,
        org_id: str,
        *,
        estimated_cost_usd: float = 0.0,
        user_id: str | None = None,
        goal_id: str | None = None,
    ) -> BudgetStatus:
        if not getattr(settings, "ai_budget_enforcement_enabled", True):
            return BudgetStatus(allowed=True, reason="enforcement_disabled")

        monthly_limit, daily_limit, user_limit, goal_limit = self._limits(org_id)
        soft_ratio = float(getattr(settings, "ai_budget_soft_ratio", 0.8) or 0.8)

        day = self._day_key()
        month = self._month_key()
        monthly_used = self._get(org_id, f"month:{month}")
        daily_used = self._get(org_id, f"day:{day}")
        user_used = self._get(org_id, f"user:{user_id}:{day}") if user_id else 0.0
        goal_used = self._get(org_id, f"goal:{goal_id}") if goal_id else 0.0

        projected_m = monthly_used + estimated_cost_usd
        projected_d = daily_used + estimated_cost_usd

        if projected_m > monthly_limit:
            log_event("ai.budget.hard_block", org_id=org_id, scope="monthly", used=monthly_used, limit=monthly_limit)
            return BudgetStatus(
                allowed=False,
                hard_blocked=True,
                reason="monthly_budget_exceeded",
                monthly_used=monthly_used,
                daily_used=daily_used,
                monthly_limit=monthly_limit,
                daily_limit=daily_limit,
                remaining_usd=max(0.0, monthly_limit - monthly_used),
            )
        if projected_d > daily_limit:
            log_event("ai.budget.hard_block", org_id=org_id, scope="daily", used=daily_used, limit=daily_limit)
            return BudgetStatus(
                allowed=False,
                hard_blocked=True,
                reason="daily_budget_exceeded",
                monthly_used=monthly_used,
                daily_used=daily_used,
                monthly_limit=monthly_limit,
                daily_limit=daily_limit,
                remaining_usd=max(0.0, daily_limit - daily_used),
            )
        if user_id and user_used + estimated_cost_usd > user_limit:
            return BudgetStatus(
                allowed=False,
                hard_blocked=True,
                reason="user_daily_budget_exceeded",
                monthly_used=monthly_used,
                daily_used=daily_used,
                monthly_limit=monthly_limit,
                daily_limit=daily_limit,
            )
        if goal_id and goal_used + estimated_cost_usd > goal_limit:
            return BudgetStatus(
                allowed=False,
                hard_blocked=True,
                reason="goal_budget_exceeded",
                monthly_used=monthly_used,
                daily_used=daily_used,
                monthly_limit=monthly_limit,
                daily_limit=daily_limit,
            )

        soft = projected_d >= daily_limit * soft_ratio or projected_m >= monthly_limit * soft_ratio
        if soft:
            log_event("ai.budget.soft_warning", org_id=org_id, daily_used=daily_used, monthly_used=monthly_used)
        return BudgetStatus(
            allowed=True,
            soft_warning=soft,
            prefer_cheap=soft,
            prefer_skip_llm=soft and projected_d >= daily_limit * 0.95,
            reason="soft_limit" if soft else "ok",
            monthly_used=monthly_used,
            daily_used=daily_used,
            monthly_limit=monthly_limit,
            daily_limit=daily_limit,
            remaining_usd=max(0.0, min(monthly_limit - monthly_used, daily_limit - daily_used)),
        )

    def commit(
        self,
        org_id: str,
        cost_usd: float,
        *,
        user_id: str | None = None,
        goal_id: str | None = None,
    ) -> None:
        if cost_usd <= 0:
            return
        day = self._day_key()
        month = self._month_key()
        self._set(org_id, f"day:{day}", self._get(org_id, f"day:{day}") + cost_usd, ttl=90000)
        self._set(org_id, f"month:{month}", self._get(org_id, f"month:{month}") + cost_usd, ttl=40 * 86400)
        if user_id:
            self._set(org_id, f"user:{user_id}:{day}", self._get(org_id, f"user:{user_id}:{day}") + cost_usd, ttl=90000)
        if goal_id:
            self._set(org_id, f"goal:{goal_id}", self._get(org_id, f"goal:{goal_id}") + cost_usd, ttl=7 * 86400)


ai_budget_manager = AIBudgetManager()
