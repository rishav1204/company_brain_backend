from __future__ import annotations

from app.modules.finance_os.analytics.read_models import workflow_read_models
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.services.cache.redis_cache import cache_hit_metric, cache_miss_metric, get_cached, set_cached


class CloseAnalyticsService:
    def get(self, org_id: str, *, fiscal_period_id: str | None = None) -> dict:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        params = {"fiscal_period_id": fiscal_period_id}
        cached = get_cached(org_id, "analytics.close", params)
        if cached is not None:
            cache_hit_metric("analytics.close")
            return cached
        cache_miss_metric("analytics.close")
        close = workflow_read_models.load_close(org_id, fiscal_period_id=fiscal_period_id)
        kpi_codes = ["close.duration_days", "close.efficiency_score", "close.sla_breach_count"]
        kpis = kpi_snapshot_repository.list(org_id, kpi_codes=kpi_codes, limit=10)
        result = {"close": close, "kpis": kpis}
        set_cached(org_id, "analytics.close", result, params)
        return result


close_analytics_service = CloseAnalyticsService()
