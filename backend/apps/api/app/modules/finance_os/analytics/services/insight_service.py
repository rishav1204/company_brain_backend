from __future__ import annotations

from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


class InsightService:
    def list(self, org_id: str, *, severity: str | None = None, limit: int = 50) -> list[dict]:
        if not analytics_schema_repository.schema_ready():
            raise ValueError("finance_analytics schema not ready")
        return insight_repository.list(org_id, severity=severity, limit=limit)


insight_service = InsightService()
