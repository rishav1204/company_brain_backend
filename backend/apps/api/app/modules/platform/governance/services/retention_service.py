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

    def run_archival(self, org_id: str, *, resource_type: str = "audit_logs", batch_size: int = 500) -> dict:
        """Mark records past retention for archival (never hard-delete audit rows)."""
        policy = self.get_policy(org_id, resource_type)
        retain_years = int(policy.get("retain_years") or DEFAULT_RETENTION_YEARS)
        archived = 0
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    if resource_type == "audit_logs":
                        cur.execute(
                            """
                            UPDATE audit.audit_logs al
                            SET metadata = COALESCE(al.metadata, '{}'::jsonb) || '{"archived": true}'::jsonb
                            FROM (
                                SELECT id FROM audit.audit_logs
                                WHERE org_id = %s::uuid
                                  AND created_at < NOW() - (%s || ' years')::interval
                                  AND COALESCE(metadata->>'archived', 'false') <> 'true'
                                LIMIT %s
                            ) batch
                            WHERE al.id = batch.id
                            """,
                            (org_id, str(retain_years), batch_size),
                        )
                        archived = cur.rowcount
        except Exception as exc:
            log_event("governance.retention.archival_failed", org_id=org_id, error=str(exc))
            return {"status": "error", "detail": str(exc), "archived": 0}
        log_event("governance.retention.archival_completed", org_id=org_id, archived=archived, resource_type=resource_type)
        return {"status": "completed", "archived": archived, "resource_type": resource_type, "retain_years": retain_years}


retention_service = RetentionService()
