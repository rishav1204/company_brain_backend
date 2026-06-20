from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SyncAuditRepository:
    def create(
        self,
        org_id: str,
        *,
        source_event_type: str | None,
        entity_type: str | None,
        entity_id: str | None,
        mutation_type: str,
        status: str,
        trace_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.graph_sync_events (
                        id, org_id, source_event_type, entity_type, entity_id,
                        mutation_type, status, trace_id, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id::text, status, created_at::text
                    """,
                    (
                        row_id,
                        org_id,
                        source_event_type,
                        entity_type,
                        entity_id,
                        mutation_type,
                        status,
                        trace_id,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def exists_for_event(self, org_id: str, *, source_event_type: str, entity_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM finance_os.graph_sync_events
                    WHERE org_id = %s::uuid AND source_event_type = %s AND entity_id = %s
                      AND status = 'success'
                    LIMIT 1
                    """,
                    (org_id, source_event_type, entity_id),
                )
                return cur.fetchone() is not None


sync_audit_repository = SyncAuditRepository()
