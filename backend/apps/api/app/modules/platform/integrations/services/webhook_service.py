from __future__ import annotations

import json
import secrets
from uuid import uuid4

import httpx
from psycopg.types.json import Json

from app.core.config import settings
from app.modules.platform.api_gateway.engine import retry_engine
from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository
from app.modules.platform.integrations.security.credential_manager import credential_manager
from app.services.db import get_db_conn, set_rls_org


def sign_payload(secret: str, payload: bytes) -> str:
    import hashlib
    import hmac

    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class IntegrationsWebhookService:
    def schema_ready(self) -> bool:
        return webhook_repository.schema_ready()

    def create_subscription(
        self,
        org_id: str,
        *,
        endpoint_url: str,
        event_types: list[str],
    ) -> tuple[dict, str]:
        # Generate secret; store only hash (never store raw secret).
        secret_plain = "whsec_" + secrets.token_urlsafe(24)
        import hashlib

        secret_hash = hashlib.sha256(secret_plain.encode()).hexdigest()
        # Production-grade requirement: must be able to encrypt secrets at rest.
        secret_encrypted = credential_manager.encrypt_json({"secret": secret_plain})
        item = webhook_repository.create_subscription(
            org_id,
            endpoint_url=endpoint_url,
            secret_hash=secret_hash,
            secret_encrypted=secret_encrypted,
            event_types=event_types or [],
        )
        return item, secret_plain

    def list_subscriptions(self, org_id: str) -> list[dict]:
        return webhook_repository.list_subscriptions(org_id)

    def dispatch_event(self, org_id: str, event_type: str, envelope: dict) -> list[dict]:
        """
        Enqueue delivery records and attempt immediate delivery.
        """
        if not self.schema_ready():
            return []
        subs = self._matching_subscriptions(org_id, event_type)
        deliveries: list[dict] = []
        for sub in subs:
            deliveries.append(self._enqueue_and_deliver(org_id, sub, event_type, envelope))
        return deliveries

    def _matching_subscriptions(self, org_id: str, event_type: str) -> list[dict]:
        # Includes encrypted secrets for signing.
        subs = webhook_repository.list_subscriptions_with_secrets(org_id)
        out: list[dict] = []
        for s in subs:
            if not s.get("is_active"):
                continue
            types = s.get("event_types") or []
            if not types or event_type in types:
                out.append(s)
        return out

    def _enqueue_and_deliver(self, org_id: str, sub: dict, event_type: str, envelope: dict) -> dict:
        delivery_id = str(uuid4())
        event_id = str(envelope.get("event_id") or uuid4())
        body = json.dumps({"event_type": event_type, "envelope": envelope}, default=str).encode()

        secret_plain = ""
        if sub.get("secret_encrypted"):
            try:
                secret_plain = str(credential_manager.decrypt_json(str(sub["secret_encrypted"])).get("secret") or "")
            except Exception:
                secret_plain = ""
        if not secret_plain:
            raise RuntimeError("Webhook secret unavailable for signing")
        signature = sign_payload(secret_plain, body)

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.webhook_deliveries (
                      id, org_id, subscription_id, event_id, event_type, payload, signature, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, %s, 'pending')
                    RETURNING id::text AS id
                    """,
                    (delivery_id, org_id, sub["id"], event_id, event_type, Json(envelope), signature),
                )
                row = cur.fetchone() or {"id": delivery_id}

        self._deliver_now(
            org_id,
            delivery_id=delivery_id,
            target_url=str(sub["endpoint_url"]),
            body=body,
            signature=signature,
            event_type=event_type,
        )
        return row

    def _deliver_now(self, org_id: str, *, delivery_id: str, target_url: str, body: bytes, signature: str, event_type: str) -> None:
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Signature": signature,
            "X-Event-Type": event_type,
        }
        status = "delivered"
        last_error: str | None = None
        response_code: int | None = None
        response_body: str | None = None
        try:
            with httpx.Client(timeout=settings.integration_timeout_seconds) as client:
                resp = client.post(target_url, content=body, headers=headers)
                response_code = resp.status_code
                response_body = resp.text[:2000] if resp.text else None
                if resp.status_code >= 400:
                    status = "retrying"
                    last_error = f"HTTP {resp.status_code}"
        except Exception as exc:
            status = "retrying"
            last_error = str(exc)

        attempt = 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT attempt_count FROM integrations.webhook_deliveries WHERE id = %s::uuid",
                    (delivery_id,),
                )
                row = cur.fetchone()
                attempt = int(row[0]) if row else 0

        delay = retry_engine.retry_delay_seconds(attempt) if status == "retrying" else 0

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE integrations.webhook_deliveries
                    SET status=%s,
                        attempt_count = attempt_count + 1,
                        last_error=%s,
                        response_code=%s,
                        response_body=%s,
                        last_attempt_at=NOW(),
                        delivered_at = CASE WHEN %s='delivered' THEN NOW() ELSE NULL END,
                        next_retry_at = CASE WHEN %s='retrying' THEN NOW() + (INTERVAL '1 seconds' * %s) ELSE NULL END
                    WHERE id = %s::uuid
                    """,
                    (status, last_error, response_code, response_body, status, status, delay, delivery_id),
                )
        try:
            from app.modules.platform.api_gateway.events.gateway_events import gateway_events

            if status == "delivered":
                gateway_events.emit_webhook_delivered(org_id, delivery_id=delivery_id, event_type=event_type)
            elif status == "retrying" and not retry_engine.should_retry(attempt + 1):
                gateway_events.emit_webhook_failed(org_id, delivery_id=delivery_id, error=last_error or "max_retries")
        except Exception:
            pass
        # Governance audit trail (best-effort)
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="integrations.webhooks",
                action=f"integrations.webhook.delivery.{status}",
                object_ref=format_object_ref("integrations", "webhook_delivery", delivery_id),
                payload={"target_url": target_url, "event_type": event_type, "status": status, "error": last_error},
                entity_type="webhook_delivery",
                entity_id=delivery_id,
                source_service="integrations.webhooks",
            )
        except Exception:
            pass

    def process_pending_deliveries(self, org_id: str, *, limit: int = 20) -> int:
        if not self.schema_ready():
            return 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.id::text AS delivery_id,
                           d.payload,
                           d.attempt_count,
                           d.event_type,
                           s.endpoint_url,
                           s.secret_encrypted
                    FROM integrations.webhook_deliveries d
                    JOIN integrations.webhook_subscriptions s ON s.id = d.subscription_id
                    WHERE d.org_id = %s::uuid AND d.status IN ('pending','retrying')
                      AND (d.next_retry_at IS NULL OR d.next_retry_at <= NOW())
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
        processed = 0
        for row in rows:
            attempts = int(row.get("attempt_count") or 0)
            if not retry_engine.should_retry(attempts, settings.webhook_max_attempts):
                # Mark as failed terminally
                try:
                    with get_db_conn() as conn:
                        set_rls_org(conn, org_id)
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE integrations.webhook_deliveries
                                SET status='failed'
                                WHERE id = %s::uuid AND org_id = %s::uuid
                                """,
                                (row["delivery_id"], org_id),
                            )
                except Exception:
                    pass
                continue
            body = json.dumps({"event_type": row["event_type"], "envelope": row.get("payload") or {}}, default=str).encode()
            secret_plain = ""
            if row.get("secret_encrypted"):
                try:
                    secret_plain = str(credential_manager.decrypt_json(str(row["secret_encrypted"])).get("secret") or "")
                except Exception:
                    secret_plain = ""
            if not secret_plain:
                continue
            signature = sign_payload(secret_plain, body)
            self._deliver_now(
                org_id,
                delivery_id=str(row["delivery_id"]),
                target_url=str(row["endpoint_url"]),
                body=body,
                signature=signature,
                event_type=str(row["event_type"]),
            )
            processed += 1
        return processed


integrations_webhook_service = IntegrationsWebhookService()

