from __future__ import annotations

from app.modules.finance_os.analytics.repositories.kpi_trend_repository import kpi_trend_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


class TrendService:
    def list(self, org_id: str, *, kpi_code: str | None = None, period: str | None = None, limit: int = 50) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        return kpi_trend_repository.list(org_id, kpi_code=kpi_code, period_key=period, limit=limit)


trend_service = TrendService()
