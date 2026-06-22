from __future__ import annotations

from app.modules.finance_os.analytics.engine import benchmark_engine
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


class BenchmarkService:
    def compare(self, org_id: str, *, kpi_code: str) -> dict:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        return benchmark_engine.compare(org_id, kpi_code=kpi_code)


benchmark_service = BenchmarkService()
