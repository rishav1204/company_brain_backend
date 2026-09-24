from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ConnectorRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='integrations' AND table_name='connectors'
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(
        self,
        org_id: str,
        *,
        connector_type: str,
        provider_name: str,
        status: str,
        config: dict,
        encrypted_credentials: str | None,
    ) -> dict:
        connector_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integrations.connectors (
                      id, org_id, connector_type, provider_name, status, config, encrypted_credentials
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s)
                    RETURNING id::text, connector_type, provider_name, status, config, created_at::text
                    """,
                    (connector_id, org_id, connector_type, provider_name, status, Json(config or {}), encrypted_credentials),
                )
                return dict(cur.fetchone() or {"id": connector_id})

    def list(self, org_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, connector_type, provider_name, status, config, created_at::text
                    FROM integrations.connectors
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


connector_repository = ConnectorRepository()

