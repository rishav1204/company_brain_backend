from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SessionRepository:
    def create_session(
        self,
        org_id: str,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        device_info: dict | None = None,
        ip_address: str | None = None,
        rotated_from: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.sessions (
                        org_id, user_id, refresh_token_hash, expires_at,
                        device_info, ip_address, rotated_from
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s::inet, %s::uuid)
                    RETURNING id::text AS id, user_id::text AS user_id, org_id::text AS org_id,
                              expires_at, revoked, created_at
                    """,
                    (
                        org_id,
                        user_id,
                        refresh_token_hash,
                        expires_at,
                        Json(device_info or {}),
                        ip_address,
                        rotated_from,
                    ),
                )
                return cur.fetchone()

    def get_by_refresh_hash(self, refresh_token_hash: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, user_id::text AS user_id, org_id::text AS org_id,
                           expires_at, revoked, refresh_token_hash
                    FROM core.sessions
                    WHERE refresh_token_hash = %s
                    LIMIT 1
                    """,
                    (refresh_token_hash,),
                )
                return cur.fetchone()

    def revoke_session(self, org_id: str, session_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.sessions
                    SET revoked = TRUE
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id
                    """,
                    (session_id, org_id),
                )
                return cur.fetchone() is not None

    def revoke_all_for_user(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.sessions SET revoked = TRUE
                    WHERE org_id = %s::uuid AND user_id = %s::uuid AND revoked = FALSE
                    """,
                    (org_id, user_id),
                )
                return cur.rowcount

    def list_active_sessions(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, device_info, ip_address::text AS ip_address,
                           expires_at, revoked, created_at
                    FROM core.sessions
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    (org_id, user_id),
                )
                return list(cur.fetchall())
