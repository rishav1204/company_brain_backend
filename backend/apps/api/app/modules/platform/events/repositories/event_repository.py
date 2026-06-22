from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class EventRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'platform' AND table_name = 'event_store'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def append(
        self,
        *,
        org_id: str,
        event_id: str,
        event_type: str,
        source: str,
        payload: dict,
        metadata: dict | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        trace_id: str | None = None,
        actor_id: str | None = None,
        event_version: str = "v1",
        status: str = "published",
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.event_store (
                        org_id, event_id, event_type, event_version, entity_type, entity_id,
                        source, trace_id, actor_id, payload, metadata, status
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s::uuid,
                        %s, %s::uuid, %s::uuid, %s::jsonb, %s::jsonb, %s
                    )
                    RETURNING id::text AS id, created_at
                    """,
                    (
                        org_id,
                        event_id,
                        event_type,
                        event_version,
                        entity_type,
                        entity_id,
                        source,
                        trace_id,
                        actor_id,
                        Json(payload),
                        Json(metadata or {}),
                        status,
                    ),
                )
                return cur.fetchone() or {}

    def mark_processed(self, org_id: str, event_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform.event_store
                    SET status = 'processed', processed_at = NOW()
                    WHERE org_id = %s::uuid AND event_id = %s::uuid
                    """,
                    (org_id, event_id),
                )

    def list_events(
        self,
        org_id: str,
        *,
        event_type: str | None = None,
        limit: int = 50,
        from_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)
        if from_event_id:
            clauses.append("created_at > (SELECT created_at FROM platform.event_store WHERE event_id = %s::uuid AND org_id = %s::uuid)")
            params.extend([from_event_id, org_id])
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT event_id::text AS event_id, event_type, source, payload, metadata,
                           status, created_at, processed_at, trace_id::text AS trace_id
                    FROM platform.event_store
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return cur.fetchall() or []

    def list_for_org(
        self,
        org_id: str,
        *,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.list_events(org_id, event_type=event_type, limit=limit)
        return [dict(r) if not isinstance(r, dict) else r for r in rows]

    def get_by_event_id(self, org_id: str, event_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id::text AS event_id, event_type, source, payload, metadata,
                           status, created_at, processed_at, trace_id::text AS trace_id
                    FROM platform.event_store
                    WHERE org_id = %s::uuid AND event_id = %s::uuid
                    LIMIT 1
                    """,
                    (org_id, event_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


event_repository = EventRepository()
