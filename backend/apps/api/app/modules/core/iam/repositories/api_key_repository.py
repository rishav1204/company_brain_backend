import hashlib
import secrets
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyRepository:
    def create_key(
        self,
        org_id: str,
        name: str,
        scopes: list[str],
        created_by: str | None,
        expires_at: datetime | None = None,
    ) -> tuple[dict[str, Any], str]:
        raw_key = f"cb_{secrets.token_urlsafe(32)}"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.api_keys (org_id, name, hashed_key, scopes, expires_at, created_by)
                    VALUES (%s::uuid, %s, %s, %s::jsonb, %s, %s::uuid)
                    RETURNING id::text AS id, org_id::text AS org_id, name, scopes, expires_at, created_at
                    """,
                    (org_id, name, _hash_key(raw_key), Json(scopes), expires_at, created_by),
                )
                return cur.fetchone(), raw_key

    def list_keys(self, org_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, name, scopes, expires_at, revoked, created_at
                    FROM core.api_keys
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return list(cur.fetchall())

    def get_by_hash(self, hashed_key: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, name, scopes, expires_at, revoked
                    FROM core.api_keys
                    WHERE hashed_key = %s
                    LIMIT 1
                    """,
                    (hashed_key,),
                )
                return cur.fetchone()

    def revoke_key(self, org_id: str, key_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.api_keys SET revoked = TRUE
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id
                    """,
                    (key_id, org_id),
                )
                return cur.fetchone() is not None
