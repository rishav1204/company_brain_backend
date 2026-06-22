from __future__ import annotations

from app.services.db import get_db_conn


class AnalyticsSchemaRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'finance_analytics' AND table_name = 'kpi_snapshots'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None


analytics_schema_repository = AnalyticsSchemaRepository()
