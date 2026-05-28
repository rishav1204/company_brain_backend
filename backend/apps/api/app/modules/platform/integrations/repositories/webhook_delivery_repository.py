from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class WebhookDeliveryRepository:
    def list_deliveries(self, org_id: str, *, limit: int = 50, status: str | None = None) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id::text, subscription_id::text AS subscription_id, event_type, status,
                               attempt_count::int, last_error, last_attempt_at::text, delivered_at::text,
                               next_retry_at::text, created_at::text
                        FROM integrations.webhook_deliveries
                        WHERE org_id = %s::uuid AND status = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, subscription_id::text AS subscription_id, event_type, status,
                               attempt_count::int, last_error, last_attempt_at::text, delivered_at::text,
                               next_retry_at::text, created_at::text
                        FROM integrations.webhook_deliveries
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_delivery(self, org_id: str, *, delivery_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, subscription_id::text AS subscription_id, event_id::text AS event_id,
                           event_type, payload, status, attempt_count::int, last_error,
                           last_attempt_at::text, delivered_at::text, next_retry_at::text, created_at::text
                    FROM integrations.webhook_deliveries
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, delivery_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


webhook_delivery_repository = WebhookDeliveryRepository()

