from __future__ import annotations

from app.modules.finance_os.analytics.repositories.kpi_trend_repository import kpi_trend_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.services.cache.redis_cache import cache_hit_metric, cache_miss_metric, get_cached, set_cached


class TrendService:
    def list(self, org_id: str, *, kpi_code: str | None = None, period: str | None = None, limit: int = 50) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        params = {"kpi_code": kpi_code, "period": period, "limit": limit}
        cached = get_cached(org_id, "analytics.trends", params)
        if cached is not None:
            cache_hit_metric("analytics.trends")
            return cached
        cache_miss_metric("analytics.trends")
        rows = kpi_trend_repository.list(org_id, kpi_code=kpi_code, period_key=period, limit=limit)
        set_cached(org_id, "analytics.trends", rows, params)
        return rows


trend_service = TrendService()
