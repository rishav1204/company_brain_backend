from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ApiKeyRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='integrations' AND table_name='api_keys'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(self, org_id: str, *, name: str, key_hash: str, scopes: list[str]) -> dict:
        key_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.api_keys (id, org_id, name, key_hash, scopes)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                    RETURNING id::text, name, scopes, is_active, created_at::text
                    """,
                    (key_id, org_id, name, key_hash, Json(scopes or [])),
                )
                return dict(cur.fetchone() or {"id": key_id})

    def list(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, name, scopes, is_active, last_used_at::text, created_at::text, revoked_at::text
                    FROM integrations.api_keys
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def revoke(self, org_id: str, *, api_key_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE integrations.api_keys
                    SET is_active = FALSE, revoked_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, name, is_active, revoked_at::text
                    """,
                    (org_id, api_key_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": api_key_id, "status": "not_found"}

    def get_by_hash(self, key_hash: str) -> dict | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text AS org_id, name, scopes, is_active
                    FROM integrations.api_keys
                    WHERE key_hash = %s AND is_active = TRUE
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def mark_used(self, *, api_key_id: str) -> None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE integrations.api_keys
                    SET last_used_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (api_key_id,),
                )


api_key_repository = ApiKeyRepository()

