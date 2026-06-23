"""Modular memory store repository (Finance OS M27)."""
from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org
from app.services.repository_pagination import clamp_limit


class MemoryStoreRepository:
    def create_memory(
        self,
        org_id: str,
        memory_type: str,
        subject_ref: str,
        payload_jsonb: dict,
        relevance_score: float,
    ) -> dict:
        memory_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_records (id, org_id, memory_type, subject_ref, payload_jsonb, relevance_score, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, NOW())
                    RETURNING id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
                    """,
                    (memory_id, org_id, memory_type, subject_ref, Json(payload_jsonb), relevance_score),
                )
                row = cur.fetchone()
                return dict(row or {})

    def list_memory(
        self,
        org_id: str,
        subject_ref: str | None = None,
        memory_type: str | None = None,
        *,
        limit: int | None = 50,
        offset: int | None = 0,
    ) -> list[dict]:
        limit = clamp_limit(limit)
        offset = max(0, int(offset or 0))
        query = """
            SELECT id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
            FROM memory_records
            WHERE org_id = %s::uuid
        """
        params: list = [org_id]
        if subject_ref:
            query += " AND subject_ref = %s"
            params.append(subject_ref)
        if memory_type:
            query += " AND memory_type = %s"
            params.append(memory_type)
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return [dict(row) for row in cur.fetchall()]

    def list_all_for_decay(self, org_id: str, *, limit: int | None = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=2000)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
                    FROM memory_records
                    WHERE org_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(row) for row in cur.fetchall()]

    def update_memory_status_batch(self, org_id: str, memory_ids: list[str], status: str) -> int:
        if not memory_ids:
            return 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE memory_records
                    SET payload_jsonb = COALESCE(payload_jsonb, '{}'::jsonb) || jsonb_build_object('status', %s)
                    WHERE org_id = %s::uuid AND id = ANY(%s::uuid[])
                    """,
                    (status, org_id, memory_ids),
                )
                return cur.rowcount

    def update_memory_status(self, org_id: str, memory_id: str, status: str) -> None:
        self.update_memory_status_batch(org_id, [memory_id], status)


memory_store_repository = MemoryStoreRepository()
