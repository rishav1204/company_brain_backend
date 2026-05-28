from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class SubscriptionService:
    def subscribe(self, org_id: str, user_id: str, channel_key: str) -> dict:
        sid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.subscriptions (id, org_id, user_id, channel_key)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
                    ON CONFLICT (org_id, user_id, channel_key) DO NOTHING
                    RETURNING id::text, channel_key
                    """,
                    (sid, org_id, user_id, channel_key),
                )
                return dict(cur.fetchone() or {"id": sid, "channel_key": channel_key})


subscription_service = SubscriptionService()
