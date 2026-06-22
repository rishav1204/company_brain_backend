from __future__ import annotations

from app.services.db import get_db_conn


class AuditSchemaRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'finance_audit' AND table_name = 'audit_timelines'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None


audit_schema_repository = AuditSchemaRepository()
