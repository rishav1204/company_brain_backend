from __future__ import annotations

from app.modules.finance_os.analytics.repositories.anomaly_flag_repository import anomaly_flag_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


class AnomalyAnalyticsService:
    def list(self, org_id: str, *, limit: int = 20) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        return anomaly_flag_repository.list_recent(org_id, limit=limit)


anomaly_analytics_service = AnomalyAnalyticsService()
