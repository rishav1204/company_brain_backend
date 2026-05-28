from __future__ import annotations

from app.modules.platform.notifications.services.notification_service import notification_service


class DigestService:
    DIGEST_TYPES = ("daily_finance_summary", "approval_digest", "compliance_digest", "risk_digest")

    def queue_item(self, org_id: str, user_id: str, digest_type: str, payload: dict) -> None:
        if not notification_service.schema_ready():
            return
        from app.services.db import get_db_conn, set_rls_org
        from psycopg.types.json import Json
        from uuid import uuid4

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.digest_queue (id, org_id, user_id, digest_type, payload)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
                    """,
                    (str(uuid4()), org_id, user_id, digest_type, Json(payload)),
                )

    def send_approval_digest(self, org_id: str, user_id: str, items: list) -> dict | None:
        return self.send_digest(org_id, user_id, "approval_digest", items)

    def send_digest(self, org_id: str, user_id: str, digest_type: str, items: list) -> dict | None:
        return notification_service.dispatch(
            org_id,
            notification_type=digest_type,
            channel="email",
            priority="low",
            variables={"body": "\n".join(f"- {i}" for i in items), "recipient_name": "User"},
            recipient_user_id=user_id,
        )


digest_service = DigestService()
