from __future__ import annotations

from app.modules.platform.governance.retention.retention_rules import DEFAULT_RETENTION_YEARS, retention_years_for
from app.services.db import get_db_conn, set_rls_org
from app.services.logger import log_event


class RetentionService:
    def get_policy(self, org_id: str, resource_type: str) -> dict:
        years = retention_years_for(resource_type)
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT resource_type, retain_years, archive_after_days, is_active
                        FROM governance.retention_policies
                        WHERE org_id = %s::uuid AND resource_type = %s
                        LIMIT 1
                        """,
                        (org_id, resource_type),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception:
            pass
        return {"resource_type": resource_type, "retain_years": years, "archive_after_days": 365, "is_active": True}

    def schedule_archival(self, org_id: str) -> dict:
        log_event("governance.retention.archival_scheduled", org_id=org_id)
        return {"status": "scheduled", "default_years": DEFAULT_RETENTION_YEARS}


retention_service = RetentionService()
