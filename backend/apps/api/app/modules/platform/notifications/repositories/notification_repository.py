from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class NotificationRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'notifications' AND table_name = 'notifications'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def exists_for_event(
        self,
        org_id: str,
        *,
        event_id: str,
        channel: str,
        notification_type: str,
        recipient_user_id: str | None = None,
    ) -> bool:
        if not event_id:
            return False
        clauses = [
            "org_id = %s::uuid",
            "event_id = %s::uuid",
            "channel = %s",
            "notification_type = %s",
        ]
        params: list[Any] = [org_id, event_id, channel, notification_type]
        if recipient_user_id:
            clauses.append("recipient_user_id = %s::uuid")
            params.append(recipient_user_id)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM notifications.notifications WHERE {' AND '.join(clauses)} LIMIT 1",
                    tuple(params),
                )
                return cur.fetchone() is not None

    def snooze(self, org_id: str, notification_id: str, *, until_iso: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE notifications.notifications
                    SET snoozed_until = %s::timestamptz
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text
                    """,
                    (until_iso, notification_id, org_id),
                )
                return cur.fetchone() is not None

    def create(
        self,
        org_id: str,
        *,
        notification_type: str,
        channel: str,
        body: str,
        subject: str | None = None,
        recipient_user_id: str | None = None,
        recipient_address: str | None = None,
        status: str = "pending",
        priority: str = "medium",
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        event_type: str | None = None,
        event_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        nid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.notifications (
                        id, org_id, notification_type, channel, recipient_user_id, recipient_address,
                        subject, body, status, priority, related_entity_type, related_entity_id,
                        event_type, event_id, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s::uuid, %s,
                        %s, %s, %s, %s, %s, %s::uuid,
                        %s, %s::uuid, %s::jsonb
                    )
                    RETURNING id::text, status, created_at
                    """,
                    (
                        nid,
                        org_id,
                        notification_type,
                        channel,
                        recipient_user_id,
                        recipient_address,
                        subject,
                        body,
                        status,
                        priority,
                        related_entity_type,
                        related_entity_id,
                        event_type,
                        event_id,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, notification_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, notification_type, channel, subject, body, status, priority,
                           recipient_user_id::text, recipient_address, related_entity_type,
                           related_entity_id::text, metadata
                    FROM notifications.notifications
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (notification_id, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_status(self, org_id: str, notification_id: str, status: str, *, sent: bool = False) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE notifications.notifications
                    SET status = %s, sent_at = CASE WHEN %s THEN NOW() ELSE sent_at END
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (status, sent, notification_id, org_id),
                )

    def list_for_user(
        self,
        org_id: str,
        *,
        user_id: str | None = None,
        unread_only: bool = False,
        exclude_snoozed: bool = True,
        notification_type: str | None = None,
        channel: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if user_id:
            clauses.append("recipient_user_id = %s::uuid")
            params.append(user_id)
        if unread_only:
            clauses.append("acknowledged_at IS NULL")
        if exclude_snoozed:
            clauses.append("(snoozed_until IS NULL OR snoozed_until <= NOW())")
        if notification_type:
            clauses.append("notification_type = %s")
            params.append(notification_type)
        if channel:
            clauses.append("channel = %s")
            params.append(channel)
        if priority:
            clauses.append("priority = %s")
            params.append(priority)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, notification_type, channel, subject, body, status, priority,
                           related_entity_type, related_entity_id::text, acknowledged_at, created_at, sent_at
                    FROM notifications.notifications
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def acknowledge(self, org_id: str, notification_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE notifications.notifications
                    SET acknowledged_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid AND acknowledged_at IS NULL
                    RETURNING id::text
                    """,
                    (notification_id, org_id),
                )
                return cur.fetchone() is not None

    def unread_count(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt FROM notifications.notifications
                    WHERE org_id = %s::uuid AND recipient_user_id = %s::uuid
                      AND acknowledged_at IS NULL
                      AND (snoozed_until IS NULL OR snoozed_until <= NOW())
                    """,
                    (org_id, user_id),
                )
                row = cur.fetchone()
        return int((row or {}).get("cnt") or 0)

    def append_delivery_log(
        self,
        org_id: str,
        *,
        notification_id: str,
        provider: str,
        delivery_status: str,
        provider_response: dict,
        attempt_count: int,
    ) -> dict:
        did = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.delivery_logs (
                        id, org_id, notification_id, provider, delivery_status,
                        provider_response, attempt_count, last_attempt_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, NOW())
                    RETURNING id::text
                    """,
                    (did, org_id, notification_id, provider, delivery_status, Json(provider_response), attempt_count),
                )
                return dict(cur.fetchone() or {})


notification_repository = NotificationRepository()
