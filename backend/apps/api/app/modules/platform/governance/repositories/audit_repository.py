from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


def _jsonb(value: dict | None) -> Json:
    return Json(value or {})


class GovernanceAuditRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'audit_logs' AND column_name = 'trace_id'
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
        actor_type: str,
        actor_id: str,
        event_type: str,
        object_ref: str,
        payload_jsonb: dict,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        source_service: str | None = None,
    ) -> dict[str, Any]:
        audit_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if self.schema_ready():
                    cur.execute(
                        """
                        INSERT INTO audit_logs (
                            id, org_id, actor_type, actor_id, event_type, object_ref, payload_jsonb,
                            action, entity_type, entity_id, before_state, after_state,
                            request_id, trace_id, ip_address, user_agent, source_service, created_at
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb,
                            %s, %s, %s::uuid, %s::jsonb, %s::jsonb,
                            %s::uuid, %s::uuid, %s::inet, %s, %s, NOW()
                        )
                        RETURNING id::text, actor_type, actor_id, event_type, object_ref,
                                  payload_jsonb, action, entity_type, entity_id::text,
                                  before_state, after_state, request_id::text, trace_id::text,
                                  ip_address::text, user_agent, source_service, created_at
                        """,
                        (
                            audit_id,
                            org_id,
                            actor_type,
                            actor_id,
                            event_type,
                            object_ref,
                            _jsonb(payload_jsonb),
                            action or event_type,
                            entity_type,
                            entity_id,
                            _jsonb(before_state),
                            _jsonb(after_state),
                            request_id,
                            trace_id,
                            ip_address,
                            user_agent,
                            source_service,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO audit_logs (id, org_id, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, NOW())
                        RETURNING id::text, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at
                        """,
                        (audit_id, org_id, actor_type, actor_id, event_type, object_ref, _jsonb(payload_jsonb)),
                    )
                row = cur.fetchone()
                return dict(row or {})

    def list_logs(
        self,
        org_id: str,
        *,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        trace_id: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)
        if entity_type:
            clauses.append("entity_type = %s")
            params.append(entity_type)
        if entity_id:
            clauses.append("entity_id = %s::uuid")
            params.append(entity_id)
        if trace_id:
            clauses.append("trace_id = %s::uuid")
            params.append(trace_id)
        if actor_id:
            clauses.append("actor_id = %s")
            params.append(actor_id)
        params.extend([limit, offset])
        where = " AND ".join(clauses)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, actor_type, actor_id, event_type, object_ref, payload_jsonb,
                           COALESCE(action, event_type) AS action, entity_type, entity_id::text,
                           before_state, after_state, request_id::text, trace_id::text,
                           ip_address::text, user_agent, source_service, created_at
                    FROM audit_logs
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]


governance_audit_repository = GovernanceAuditRepository()
