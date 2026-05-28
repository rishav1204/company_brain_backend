from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class WebhookRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='integrations' AND table_name='webhook_subscriptions'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create_subscription(
        self,
        org_id: str,
        *,
        endpoint_url: str,
        secret_hash: str,
        secret_encrypted: str | None,
        event_types: list[str],
    ) -> dict:
        sub_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.webhook_subscriptions (
                      id, org_id, endpoint_url, secret_hash, secret_encrypted, event_types
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                    RETURNING id::text, endpoint_url, event_types, is_active, created_at::text
                    """,
                    (sub_id, org_id, endpoint_url, secret_hash, secret_encrypted, Json(event_types or [])),
                )
                return dict(cur.fetchone() or {"id": sub_id})

    def list_subscriptions(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, endpoint_url, event_types, is_active, created_at::text
                    FROM integrations.webhook_subscriptions
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_subscriptions_with_secrets(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, endpoint_url, secret_encrypted, event_types, is_active
                    FROM integrations.webhook_subscriptions
                    WHERE org_id = %s::uuid AND is_active = TRUE
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


webhook_repository = WebhookRepository()

