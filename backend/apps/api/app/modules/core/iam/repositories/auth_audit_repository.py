from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AuthAuditRepository:
    def record(
        self,
        *,
        event: str,
        success: bool = True,
        org_id: str | None = None,
        user_id: str | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        with get_db_conn() as conn:
            if org_id:
                set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.auth_audit_log (
                        org_id, user_id, event, success, reason,
                        ip_address, user_agent, session_id, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s,
                        %s::inet, %s, %s::uuid, %s::jsonb
                    )
                    """,
                    (
                        org_id,
                        user_id,
                        event,
                        success,
                        reason,
                        ip_address,
                        user_agent,
                        session_id,
                        Json(metadata or {}),
                    ),
                )

    def list_events(
        self,
        org_id: str,
        *,
        user_id: str | None = None,
        event: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if user_id:
            clauses.append("user_id = %s::uuid")
            params.append(user_id)
        if event:
            clauses.append("event = %s")
            params.append(event)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text AS id, org_id::text AS org_id, user_id::text AS user_id,
                           event, success, reason, ip_address::text AS ip_address,
                           user_agent, session_id::text AS session_id, metadata, created_at
                    FROM core.auth_audit_log
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                return list(cur.fetchall())


auth_audit_repo = AuthAuditRepository()
