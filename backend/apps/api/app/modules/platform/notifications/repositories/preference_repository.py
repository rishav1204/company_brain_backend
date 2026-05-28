from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PreferenceRepository:
    def get_preference(
        self, org_id: str, user_id: str, channel: str, notification_type: str
    ) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT enabled, quiet_hours FROM notifications.preferences
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                      AND channel = %s AND notification_type = %s
                    LIMIT 1
                    """,
                    (org_id, user_id, channel, notification_type),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def is_enabled(self, org_id: str, user_id: str, channel: str, notification_type: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT enabled FROM notifications.preferences
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                      AND channel = %s AND notification_type = %s
                    LIMIT 1
                    """,
                    (org_id, user_id, channel, notification_type),
                )
                row = cur.fetchone()
        if row is None:
            return True
        return bool(row.get("enabled"))

    def upsert(
        self,
        org_id: str,
        *,
        user_id: str,
        channel: str,
        notification_type: str,
        enabled: bool,
        quiet_hours: dict | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.preferences (
                        id, org_id, user_id, channel, notification_type, enabled, quiet_hours
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (org_id, user_id, channel, notification_type) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        quiet_hours = EXCLUDED.quiet_hours
                    RETURNING id::text, channel, notification_type, enabled
                    """,
                    (pid, org_id, user_id, channel, notification_type, enabled, Json(quiet_hours or {})),
                )
                return dict(cur.fetchone() or {})

    def list_for_user(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT channel, notification_type, enabled, quiet_hours
                    FROM notifications.preferences
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                    """,
                    (org_id, user_id),
                )
                return [dict(r) for r in cur.fetchall()]


preference_repository = PreferenceRepository()
