from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org

TTL_DAYS = {"30d": 30, "90d": 90, "180d": 180, "forever": None}


def compute_expires_at(ttl_policy: str) -> datetime | None:
    days = TTL_DAYS.get(ttl_policy)
    if days is None:
        return None
    return datetime.now(timezone.utc) + timedelta(days=days)


class EntryRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        entry_id = str(uuid4())
        ttl = data.get("ttl_policy", "90d")
        expires = compute_expires_at(ttl)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.memory_entries (
                        id, org_id, memory_type, entity_type, entity_id, title, content,
                        importance_score, importance_band, status, ttl_policy,
                        source_event_type, memory_record_id, metadata, expires_at
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s::uuid, %s, %s,
                        %s, %s, %s, %s, %s, %s::uuid, %s::jsonb, %s
                    )
                    RETURNING id::text, memory_type, entity_type, entity_id::text AS entity_id,
                              title, content, importance_score::float8 AS importance_score,
                              importance_band, status, ttl_policy, created_at::text
                    """,
                    (
                        entry_id,
                        org_id,
                        data["memory_type"],
                        data.get("entity_type"),
                        data.get("entity_id"),
                        data["title"],
                        data["content"],
                        data.get("importance_score", 0),
                        data.get("importance_band", "medium"),
                        data.get("status", "active"),
                        ttl,
                        data.get("source_event_type"),
                        data.get("memory_record_id"),
                        Json(data.get("metadata") or {}),
                        expires,
                    ),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, entry_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, memory_type, entity_type, entity_id::text AS entity_id,
                           title, content, importance_score::float8 AS importance_score,
                           importance_band, status, ttl_policy, metadata, created_at::text
                    FROM finance_os.memory_entries
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, entry_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_active(
        self,
        org_id: str,
        *,
        memory_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        where = ["org_id = %s::uuid", "status = 'active'"]
        params: list = [org_id]
        if memory_type:
            where.append("memory_type = %s")
            params.append(memory_type)
        if entity_type:
            where.append("entity_type = %s")
            params.append(entity_type)
        if entity_id:
            where.append("entity_id = %s::uuid")
            params.append(entity_id)
        params.append(min(limit, 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, memory_type, entity_type, entity_id::text AS entity_id,
                           title, content, importance_score::float8 AS importance_score,
                           importance_band, created_at::text
                    FROM finance_os.memory_entries
                    WHERE {' AND '.join(where)}
                    ORDER BY importance_score DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def update_status(self, org_id: str, entry_id: str, status: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.memory_entries
                    SET status = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, org_id, entry_id),
                )

    def update_content(self, org_id: str, entry_id: str, *, title: str | None, content: str | None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.memory_entries
                    SET title = COALESCE(%s, title), content = COALESCE(%s, content), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, title, content, status
                    """,
                    (title, content, org_id, entry_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_for_decay(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, memory_type, ttl_policy, status, expires_at, memory_record_id::text AS memory_record_id
                    FROM finance_os.memory_entries
                    WHERE org_id = %s::uuid AND status = 'active' AND ttl_policy != 'forever'
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def count_by_entity(self, org_id: str, *, entity_type: str, entity_id: str, memory_type: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt FROM finance_os.memory_entries
                    WHERE org_id = %s::uuid AND entity_type = %s AND entity_id = %s::uuid
                      AND memory_type = %s AND status = 'active'
                    """,
                    (org_id, entity_type, entity_id, memory_type),
                )
                row = cur.fetchone()
                return int(row["cnt"]) if row else 0

    def summary_by_type(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT memory_type, COUNT(*)::int AS cnt,
                           AVG(importance_score)::float8 AS avg_importance
                    FROM finance_os.memory_entries
                    WHERE org_id = %s::uuid AND status = 'active'
                    GROUP BY memory_type
                    ORDER BY cnt DESC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]


entry_repository = EntryRepository()
