from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from psycopg.types.json import Json

from app.core.config import settings
from app.modules.platform.events.services.retry_service import next_retry_at, should_retry
from app.modules.platform.integrations.security.credential_manager import credential_manager
from app.modules.platform.integrations.security.url_safety import UnsafeUrlError, validate_outbound_url
from app.services.db import get_db_conn, set_rls_org


def sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _encrypt_secret(secret: str) -> tuple[str, dict]:
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    metadata = {"secret_encrypted": credential_manager.encrypt_json({"secret": secret})}
    return secret_hash, metadata


def _decrypt_secret(row: dict) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    encrypted = metadata.get("secret_encrypted")
    if encrypted:
        try:
            return str(credential_manager.decrypt_json(str(encrypted)).get("secret") or "")
        except Exception:
            pass
    legacy = str(row.get("secret") or "")
    if legacy and not legacy.isdigit() and len(legacy) == 64:
        return ""
    return legacy


class WebhookService:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'platform' AND table_name = 'webhook_subscriptions'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create_subscription(
        self,
        *,
        org_id: str,
        name: str,
        target_url: str,
        secret: str,
        event_types: list[str],
        rate_limit_per_minute: int = 60,
    ) -> dict:
        target_url = validate_outbound_url(target_url)
        secret_plain = secret.strip() or ("whsec_" + secrets.token_urlsafe(24))
        secret_hash, metadata = _encrypt_secret(secret_plain)
        sub_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.webhook_subscriptions (
                        id, org_id, name, target_url, secret, event_types, rate_limit_per_minute, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::text[], %s, %s::jsonb)
                    RETURNING id::text AS id, name, target_url, event_types, is_active, created_at
                    """,
                    (sub_id, org_id, name, target_url, secret_hash, event_types, rate_limit_per_minute, Json(metadata)),
                )
                return cur.fetchone() or {"id": sub_id}

    def list_subscriptions(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, name, target_url, event_types, is_active, rate_limit_per_minute, created_at
                    FROM platform.webhook_subscriptions
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return cur.fetchall() or []

    def dispatch_event(self, org_id: str, event_type: str, envelope: dict) -> list[dict]:
        if not self.schema_ready():
            return []
        subs = self._matching_subscriptions(org_id, event_type)
        deliveries: list[dict] = []
        for sub in subs:
            delivery = self._enqueue_delivery(org_id, sub, event_type, envelope)
            deliveries.append(delivery)
        return deliveries

    def _matching_subscriptions(self, org_id: str, event_type: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, target_url, secret, event_types, metadata
                    FROM platform.webhook_subscriptions
                    WHERE org_id = %s::uuid AND is_active = TRUE
                    """,
                    (org_id,),
                )
                rows = cur.fetchall() or []
        matched = [r for r in rows if not r.get("event_types") or event_type in (r.get("event_types") or [])]
        for row in matched:
            row["secret_plain"] = _decrypt_secret(row)
        return matched

    def _count_recent_deliveries(self, org_id: str, subscription_id: str, *, minutes: int = 1) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM platform.webhook_deliveries
                    WHERE org_id = %s::uuid AND subscription_id = %s::uuid
                      AND created_at > NOW() - (%s || ' minutes')::interval
                    """,
                    (org_id, subscription_id, str(minutes)),
                )
                row = cur.fetchone()
        return int((row or {}).get("cnt") or 0)

    def _enqueue_delivery(self, org_id: str, sub: dict, event_type: str, envelope: dict) -> dict:
        limit = int(sub.get("rate_limit_per_minute") or 60)
        if self._count_recent_deliveries(org_id, sub["id"]) >= limit:
            return {"id": None, "status": "rate_limited", "subscription_id": sub["id"]}
        delivery_id = str(uuid4())
        event_id = str(envelope.get("event_id", uuid4()))
        body = json.dumps({"event_type": event_type, "envelope": envelope}, default=str).encode()
        secret_plain = str(sub.get("secret_plain") or _decrypt_secret(sub))
        if not secret_plain:
            raise RuntimeError("Webhook secret unavailable for signing")
        signature = sign_payload(secret_plain, body)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.webhook_deliveries (
                        id, org_id, subscription_id, event_id, event_type, payload, signature, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, %s, 'pending')
                    RETURNING id::text AS id
                    """,
                    (delivery_id, org_id, sub["id"], event_id, event_type, Json(envelope), signature),
                )
                row = cur.fetchone() or {"id": delivery_id}
        self._deliver_now(org_id, {**sub, "delivery_id": row["id"], "secret_plain": secret_plain}, event_type, envelope, body, signature)
        return row

    def _deliver_now(
        self,
        org_id: str,
        sub: dict,
        event_type: str,
        envelope: dict,
        body: bytes,
        signature: str,
    ) -> None:
        delivery_id = sub["delivery_id"]
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Event-Type": event_type,
        }
        status = "delivered"
        last_error = None
        try:
            safe_url = validate_outbound_url(str(sub["target_url"]))
            with httpx.Client(timeout=settings.integration_timeout_seconds) as client:
                resp = client.post(safe_url, content=body, headers=headers)
                if resp.status_code >= 400:
                    status = "retrying"
                    last_error = f"HTTP {resp.status_code}"
        except (UnsafeUrlError, Exception) as exc:
            status = "retrying"
            last_error = str(exc)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform.webhook_deliveries
                    SET status = %s, attempt_count = attempt_count + 1, last_error = %s,
                        delivered_at = CASE WHEN %s = 'delivered' THEN NOW() ELSE NULL END,
                        next_retry_at = CASE WHEN %s = 'retrying' THEN NOW() + INTERVAL '5 minutes' ELSE NULL END
                    WHERE id = %s::uuid
                    """,
                    (status, last_error, status, status, delivery_id),
                )
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref
            from app.services.metrics import metrics_store

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="platform.webhooks",
                action=f"webhook.delivery.{status}",
                object_ref=format_object_ref("platform", "webhook_delivery", delivery_id),
                payload={
                    "event_type": event_type,
                    "target_url": sub.get("target_url"),
                    "status": status,
                    "error": last_error,
                },
                entity_type="webhook_delivery",
                entity_id=delivery_id,
                source_service="platform.webhooks",
            )
            metrics_store.incr_governance_webhook_delivery()
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
                    SELECT d.id::text AS delivery_id, d.payload, d.attempt_count, d.event_type,
                           s.target_url, s.secret, s.metadata
                    FROM platform.webhook_deliveries d
                    JOIN platform.webhook_subscriptions s ON s.id = d.subscription_id
                    WHERE d.org_id = %s::uuid AND d.status IN ('pending', 'retrying')
                      AND (d.next_retry_at IS NULL OR d.next_retry_at <= NOW())
                    ORDER BY d.created_at ASC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                rows = cur.fetchall() or []
        processed = 0
        for row in rows:
            if not should_retry(int(row.get("attempt_count") or 0), settings.webhook_max_attempts):
                continue
            envelope = row.get("payload") or {}
            body = json.dumps({"event_type": row["event_type"], "envelope": envelope}, default=str).encode()
            secret_plain = _decrypt_secret(row)
            signature = sign_payload(secret_plain, body)
            self._deliver_now(
                org_id,
                {
                    "delivery_id": row["delivery_id"],
                    "target_url": row["target_url"],
                    "secret_plain": secret_plain,
                },
                row["event_type"],
                envelope,
                body,
                signature,
            )
            processed += 1
        return processed


webhook_service = WebhookService()
