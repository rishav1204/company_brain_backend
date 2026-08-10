from datetime import datetime
from ipaddress import ip_address as parse_ip
from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


def _safe_inet(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"testclient", "unknown", "localhost"}:
        return None
    try:
        parse_ip(text)
        return text
    except ValueError:
        return None


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
                        _safe_inet(ip_address),
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
                    FROM core.get_session_by_refresh_hash(%s)
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

    def consume_refresh_session(self, refresh_token_hash: str) -> tuple[dict[str, Any] | None, bool]:
        """Atomically revoke session by refresh hash. Returns (session, reuse_detected)."""
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, user_id::text AS user_id, org_id::text AS org_id,
                           expires_at, revoked, reuse_detected
                    FROM core.consume_session_by_refresh_hash(%s)
                    """,
                    (refresh_token_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None, False
                if row.get("reuse_detected"):
                    return None, True
                return row, False

    def revoke_all_for_user(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            return self.revoke_all_for_user_conn(conn, org_id, user_id)

    def revoke_all_for_user_conn(self, conn, org_id: str, user_id: str) -> int:
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

    def touch_last_active(self, org_id: str, session_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.sessions SET last_active_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid AND revoked = FALSE
                    """,
                    (session_id, org_id),
                )

    def count_active_sessions(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM core.sessions
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                      AND revoked = FALSE AND expires_at > NOW()
                    """,
                    (org_id, user_id),
                )
                row = cur.fetchone()
                return int((row or {}).get("cnt") or 0)

    def revoke_oldest_sessions(self, org_id: str, user_id: str, *, keep: int) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.sessions SET revoked = TRUE
                    WHERE id IN (
                        SELECT id FROM core.sessions
                        WHERE org_id = %s::uuid AND user_id = %s::uuid
                          AND revoked = FALSE AND expires_at > NOW()
                        ORDER BY created_at ASC
                        OFFSET %s
                    )
                    """,
                    (org_id, user_id, max(0, keep)),
                )
                return cur.rowcount

    def is_session_active(self, org_id: str, session_id: str) -> bool:
        """SEC-02: validate access JWT session_id against live session row."""
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM core.sessions
                    WHERE id = %s::uuid AND org_id = %s::uuid
                      AND revoked = FALSE AND expires_at > NOW()
                    LIMIT 1
                    """,
                    (session_id, org_id),
                )
                return cur.fetchone() is not None

    def list_active_sessions(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, device_info, ip_address::text AS ip_address,
                           expires_at, revoked, created_at, last_active_at
                    FROM core.sessions
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    (org_id, user_id),
                )
                return list(cur.fetchall())
