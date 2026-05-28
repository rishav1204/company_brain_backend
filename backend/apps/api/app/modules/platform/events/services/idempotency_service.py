from __future__ import annotations

import hashlib
import json
from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PlatformIdempotencyService:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'platform' AND table_name = 'idempotency_keys'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def _hash_request(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_cached(self, org_id: str, scope: str, idempotency_key: str) -> dict | None:
        if not self.schema_ready():
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT response_payload, request_hash
                    FROM platform.idempotency_keys
                    WHERE org_id = %s::uuid AND scope = %s AND idempotency_key = %s
                      AND expires_at > NOW()
                    """,
                    (org_id, scope, idempotency_key),
                )
                row = cur.fetchone()
        if not row:
            return None
        return row.get("response_payload") if isinstance(row.get("response_payload"), dict) else None

    def store(
        self,
        org_id: str,
        scope: str,
        idempotency_key: str,
        *,
        request_payload: dict,
        response_payload: dict,
        ttl_days: int = 7,
    ) -> None:
        if not self.schema_ready():
            return
        request_hash = self._hash_request(request_payload)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.idempotency_keys (
                        org_id, idempotency_key, scope, request_hash, response_payload, expires_at
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s::jsonb, NOW() + (%s || ' days')::interval)
                    ON CONFLICT (org_id, scope, idempotency_key) DO UPDATE
                    SET response_payload = EXCLUDED.response_payload,
                        request_hash = EXCLUDED.request_hash,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (org_id, idempotency_key, scope, request_hash, Json(response_payload), str(ttl_days)),
                )

    def check_and_store(
        self,
        org_id: str,
        scope: str,
        idempotency_key: str,
        *,
        request_payload: dict,
    ) -> tuple[bool, dict | None]:
        cached = self.get_cached(org_id, scope, idempotency_key)
        if cached is not None:
            return True, cached
        return False, None


platform_idempotency_service = PlatformIdempotencyService()
