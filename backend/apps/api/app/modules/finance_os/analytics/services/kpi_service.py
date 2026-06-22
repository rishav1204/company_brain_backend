from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository


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
        return kpi_snapshot_repository.list(org_id, kpi_codes=kpi_codes, snapshot_date=snapshot_date, limit=limit)


kpi_service = KpiService()
