from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.services.cache.redis_cache import cache_hit_metric, cache_miss_metric, get_cached, set_cached


class KpiService:
    def list(
        self,
        org_id: str,
        *,
        kpi_codes: list[str] | None = None,
        snapshot_date: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        params = {
            "kpi_codes": sorted(kpi_codes) if kpi_codes else None,
            "snapshot_date": snapshot_date or date.today().isoformat(),
            "limit": limit,
        }
        cached = get_cached(org_id, "analytics.kpis", params)
        if cached is not None:
            cache_hit_metric("analytics.kpis")
            return cached
        cache_miss_metric("analytics.kpis")
        rows = kpi_snapshot_repository.list(
            org_id,
            kpi_codes=kpi_codes,
            snapshot_date=snapshot_date,
            limit=limit,
        )
        set_cached(org_id, "analytics.kpis", rows, params)
        return rows


kpi_service = KpiService()
