from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SyncRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='integrations' AND table_name='sync_jobs'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create_job(self, org_id: str, *, connector_id: str, sync_type: str, metadata: dict) -> dict:
        job_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.sync_jobs (id, org_id, connector_id, sync_type, metadata)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
                    RETURNING id::text, connector_id::text AS connector_id, sync_type, status, created_at::text
                    """,
                    (job_id, org_id, connector_id, sync_type, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": job_id})

    def list_jobs(self, org_id: str, *, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, connector_id::text AS connector_id, sync_type, status,
                           started_at::text, completed_at::text, metadata, created_at::text
                    FROM integrations.sync_jobs
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


sync_repository = SyncRepository()

