from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class EvidenceRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'audit' AND table_name = 'evidence_links'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def link(
        self,
        org_id: str,
        *,
        entity_type: str,
        entity_id: str,
        evidence_type: str,
        evidence_ref: str,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        link_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit.evidence_links (
                        id, org_id, entity_type, entity_id, evidence_type, evidence_ref, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s::uuid, %s::jsonb)
                    RETURNING id::text, entity_type, entity_id::text, evidence_type, evidence_ref::text, created_at
                    """,
                    (link_id, org_id, entity_type, entity_id, evidence_type, evidence_ref, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})

    def list_for_entity(self, org_id: str, *, entity_type: str, entity_id: str, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, evidence_type, evidence_ref::text, metadata, created_at
                    FROM audit.evidence_links
                    WHERE org_id = %s::uuid AND entity_type = %s AND entity_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, entity_type, entity_id),
                )
                return [dict(row) for row in cur.fetchall()]


evidence_repository = EvidenceRepository()
