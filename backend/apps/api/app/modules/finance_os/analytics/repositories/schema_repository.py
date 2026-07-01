from __future__ import annotations

from app.services.schema_registry import table_ready


class AnalyticsSchemaRepository:
    def schema_ready(self) -> bool:
        return table_ready("finance_analytics", "kpi_snapshots")


analytics_schema_repository = AnalyticsSchemaRepository()
