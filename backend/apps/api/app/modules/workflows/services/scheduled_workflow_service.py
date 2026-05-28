from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.modules.workflows.services.workflow_service import workflow_service
from app.services.db import get_db_conn, set_rls_org


class ScheduledWorkflowService:
    def list_due(self, org_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, workflow_key, cron_expression, last_run_at, metadata
                    FROM workflow.scheduled_workflows
                    WHERE org_id = %s::uuid AND is_active = TRUE
                    """,
                    (org_id,),
                )
                rows = cur.fetchall() or []
        return [r for r in rows if self._is_due(r)]

    def _is_due(self, row: dict) -> bool:
        last = row.get("last_run_at")
        if last is None:
            return True
        if isinstance(last, datetime):
            elapsed_hours = (datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            return elapsed_hours >= 20
        return True

    def run_due(self, org_id: str, *, trace_id: str | None = None) -> list[dict]:
        if not workflow_service.schema_ready():
            return []
        started: list[dict] = []
        for row in self.list_due(org_id):
            key = str(row.get("workflow_key", ""))
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            inst = workflow_service.start_workflow(
                org_id=org_id,
                workflow_key=key,
                entity_type="scheduled",
                entity_id=f"scheduled:{key}",
                metadata={**meta, "scheduled": True},
                trace_id=trace_id,
            )
            self._touch_last_run(org_id, row["id"])
            started.append(inst)
        return started

    def _touch_last_run(self, org_id: str, scheduled_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.scheduled_workflows
                    SET last_run_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (scheduled_id, org_id),
                )


scheduled_workflow_service = ScheduledWorkflowService()
