from __future__ import annotations

from app.services.db import get_db_conn


class ReportingSchemaRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'erp_reporting' AND table_name = 'trial_balance_mv'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None


reporting_schema_repository = ReportingSchemaRepository()
