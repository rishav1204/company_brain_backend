from __future__ import annotations

from app.modules.finance_os.analytics.engine import benchmark_engine
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository
from app.services.cache.redis_cache import cache_hit_metric, cache_miss_metric, get_cached, set_cached


class BenchmarkService:
    def compare(self, org_id: str, *, kpi_code: str) -> dict:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        params = {"kpi_code": kpi_code}
        cached = get_cached(org_id, "analytics.benchmark", params)
        if cached is not None:
            cache_hit_metric("analytics.benchmark")
            return cached
        cache_miss_metric("analytics.benchmark")
        result = benchmark_engine.compare(org_id, kpi_code=kpi_code)
        set_cached(org_id, "analytics.benchmark", result, params)
        return result

    def list(self, org_id: str, *, kpi_code: str | None = None, limit: int = 50) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        if kpi_code:
            return [self.compare(org_id, kpi_code=kpi_code)]
        params = {"limit": limit}
        cached = get_cached(org_id, "analytics.benchmark", params)
        if cached is not None:
            cache_hit_metric("analytics.benchmark")
            return cached
        cache_miss_metric("analytics.benchmark")
        limit = max(1, min(int(limit or 50), 100))
        snapshots = kpi_snapshot_repository.list(org_id, limit=500)
        codes: list[str] = []
        seen: set[str] = set()
        for row in snapshots:
            code = str(row.get("kpi_code") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
            if len(codes) >= limit:
                break
        result = [benchmark_engine.compare(org_id, kpi_code=code) for code in codes]
        set_cached(org_id, "analytics.benchmark", result, params)
        return result


benchmark_service = BenchmarkService()
