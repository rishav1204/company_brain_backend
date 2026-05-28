from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class IngestionRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='integrations' AND table_name='ingestion_records'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(self, org_id: str, *, source_type: str, source_reference: str | None, payload: dict, status: str) -> dict:
        rec_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.ingestion_records (id, org_id, source_type, source_reference, payload, status)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s)
                    RETURNING id::text, source_type, source_reference, status, created_at::text
                    """,
                    (rec_id, org_id, source_type, source_reference, Json(payload or {}), status),
                )
                return dict(cur.fetchone() or {"id": rec_id})

    def list(self, org_id: str, *, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_reference, status, created_at::text
                    FROM integrations.ingestion_records
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


ingestion_repository = IngestionRepository()

