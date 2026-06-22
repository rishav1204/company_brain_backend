from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.modules.finance_os.audit_explorer.repositories.schema_repository import audit_schema_repository
from app.modules.finance_os.audit_explorer.validators.ai_context_validator import sanitize_metadata
from app.services.db import get_db_conn, set_rls_org


class TimelineRepository:
    def schema_ready(self) -> bool:
        return audit_schema_repository.schema_ready()

    def upsert(
        self,
        org_id: str,
        *,
        object_type: str,
        object_id: str,
        event_type: str,
        actor_id: str | None = None,
        event_timestamp: datetime | str | None = None,
        metadata: dict | None = None,
        source_audit_log_id: str | None = None,
        source_event_id: str | None = None,
        trace_id: str | None = None,
        object_ref: str | None = None,
    ) -> dict[str, Any]:
        if not self.schema_ready():
            return {"id": "skipped", "status": "schema_not_ready"}
        safe_meta = sanitize_metadata(metadata)
        row_id = str(uuid4())
        ts = event_timestamp or datetime.utcnow()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if source_audit_log_id:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.audit_timelines (
                            id, org_id, object_type, object_id, event_type, actor_id,
                            event_timestamp, metadata, source_audit_log_id, source_event_id,
                            trace_id, object_ref
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s::uuid, %s, %s::uuid,
                            %s, %s::jsonb, %s::uuid, %s::uuid, %s::uuid, %s
                        )
                        ON CONFLICT DO NOTHING
                        RETURNING id::text, object_type, object_id::text, event_type, event_timestamp
                        """,
                        (
                            row_id,
                            org_id,
                            object_type,
                            object_id,
                            event_type,
                            actor_id,
                            ts,
                            Json(safe_meta),
                            source_audit_log_id,
                            source_event_id,
                            trace_id,
                            object_ref,
                        ),
                    )
                elif source_event_id:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.audit_timelines (
                            id, org_id, object_type, object_id, event_type, actor_id,
                            event_timestamp, metadata, source_audit_log_id, source_event_id,
                            trace_id, object_ref
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s::uuid, %s, %s::uuid,
                            %s, %s::jsonb, NULL, %s::uuid, %s::uuid, %s
                        )
                        ON CONFLICT DO NOTHING
                        RETURNING id::text, object_type, object_id::text, event_type, event_timestamp
                        """,
                        (
                            row_id,
                            org_id,
                            object_type,
                            object_id,
                            event_type,
                            actor_id,
                            ts,
                            Json(safe_meta),
                            source_event_id,
                            trace_id,
                            object_ref,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO finance_audit.audit_timelines (
                            id, org_id, object_type, object_id, event_type, actor_id,
                            event_timestamp, metadata, trace_id, object_ref
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s::uuid, %s, %s::uuid,
                            %s, %s::jsonb, %s::uuid, %s
                        )
                        RETURNING id::text, object_type, object_id::text, event_type, event_timestamp
                        """,
                        (
                            row_id,
                            org_id,
                            object_type,
                            object_id,
                            event_type,
                            actor_id,
                            ts,
                            Json(safe_meta),
                            trace_id,
                            object_ref,
                        ),
                    )
                row = cur.fetchone()
                if row:
                    return dict(row)
                if source_audit_log_id:
                    cur.execute(
                        """
                        SELECT id::text, object_type, object_id::text, event_type, event_timestamp
                        FROM finance_audit.audit_timelines
                        WHERE org_id = %s::uuid AND source_audit_log_id = %s::uuid
                        LIMIT 1
                        """,
                        (org_id, source_audit_log_id),
                    )
                elif source_event_id:
                    cur.execute(
                        """
                        SELECT id::text, object_type, object_id::text, event_type, event_timestamp
                        FROM finance_audit.audit_timelines
                        WHERE org_id = %s::uuid AND source_event_id = %s::uuid
                          AND object_type = %s AND object_id = %s::uuid AND event_type = %s
                        LIMIT 1
                        """,
                        (org_id, source_event_id, object_type, object_id, event_type),
                    )
                else:
                    return {"id": row_id, "object_type": object_type, "object_id": object_id, "event_type": event_type}
                existing = cur.fetchone()
                return dict(existing) if existing else {"id": row_id}

    def list_for_object(
        self,
        org_id: str,
        *,
        object_type: str,
        object_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, object_type, object_id::text, event_type,
                           actor_id::text, event_timestamp, metadata, source_audit_log_id::text,
                           source_event_id::text, trace_id::text, object_ref, created_at
                    FROM finance_audit.audit_timelines
                    WHERE org_id = %s::uuid AND object_type = %s AND object_id = %s::uuid
                    ORDER BY event_timestamp ASC, created_at ASC
                    LIMIT %s OFFSET %s
                    """,
                    (org_id, object_type, object_id, limit, offset),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_by_trace(self, org_id: str, *, trace_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, object_type, object_id::text, event_type,
                           actor_id::text, event_timestamp, metadata, trace_id::text, object_ref
                    FROM finance_audit.audit_timelines
                    WHERE org_id = %s::uuid AND trace_id = %s::uuid
                    ORDER BY event_timestamp ASC
                    LIMIT %s
                    """,
                    (org_id, trace_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def search(
        self,
        org_id: str,
        *,
        q: str | None = None,
        object_type: str | None = None,
        actor_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if object_type:
            clauses.append("object_type = %s")
            params.append(object_type)
        if actor_id:
            clauses.append("actor_id = %s::uuid")
            params.append(actor_id)
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)
        if q:
            clauses.append("(metadata::text ILIKE %s OR object_ref ILIKE %s OR event_type ILIKE %s)")
            pattern = f"%{q}%"
            params.extend([pattern, pattern, pattern])
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, object_type, object_id::text, event_type,
                           actor_id::text, event_timestamp, metadata, object_ref, trace_id::text
                    FROM finance_audit.audit_timelines
                    WHERE {' AND '.join(clauses)}
                    ORDER BY event_timestamp DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]


timeline_repository = TimelineRepository()
